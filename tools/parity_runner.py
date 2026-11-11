#!/usr/bin/env python3
"""Run cross-backend parity checks for TinyLanguage fixtures."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import difflib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Iterable, Sequence

from tiny_language import (
    TinyLangError,
    _format_error_for_source,
    compile_and_run,
    compile_to_c_executable,
    run_with_llvm_jit,
    run_with_native_backend,
)
from tools.output_normalization import NormalizationOptions, normalize_output

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_BACKENDS = ("interpreter", "native", "llvm", "c")


@dataclass(frozen=True)
class FixtureMetadata:
    """Metadata attached to a parity fixture."""

    backends: tuple[str, ...] | None = None
    skip_backends: tuple[str, ...] = ()
    expected_exit_code: int = 0
    error_contains: str = ""


@dataclass(frozen=True)
class Fixture:
    """Represents a parity fixture on disk."""

    name: str
    path: pathlib.Path
    metadata: FixtureMetadata


@dataclass
class BackendResult:
    """Captured output from a backend run."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    skipped: bool = False
    skip_reason: str = ""


def _module_namespace_for_path(path: pathlib.Path) -> str:
    try:
        rel = path.resolve().relative_to(pathlib.Path.cwd())
        return ".".join(rel.with_suffix("").parts)
    except Exception:  # noqa: BLE001 - fallback for non-relative paths
        return path.stem


def _load_metadata(path: pathlib.Path) -> FixtureMetadata:
    meta_path = path.with_suffix(".meta.json")
    if not meta_path.exists():
        return FixtureMetadata()
    raw = json.loads(meta_path.read_text(encoding="utf-8"))
    backends = tuple(raw.get("backends", [])) or None
    skip_backends = tuple(raw.get("skip_backends", []))
    expected_exit_code = raw.get("expected_exit_code", 0)
    error_contains = raw.get("error_contains", "")
    if (type(expected_exit_code) is not int or expected_exit_code not in (0, 1)
            or not isinstance(error_contains, str)
            or (expected_exit_code and not error_contains)):
        raise ValueError(f"{meta_path}: errors require exit code 1 and a diagnostic substring")
    if any(name not in DEFAULT_BACKENDS for name in (*(backends or ()), *skip_backends)):
        raise ValueError(f"{meta_path}: unknown backend")
    return FixtureMetadata(backends=backends, skip_backends=skip_backends,
                           expected_exit_code=expected_exit_code, error_contains=error_contains)


def _discover_fixtures(paths: Sequence[pathlib.Path]) -> list[Fixture]:
    fixtures: list[Fixture] = []
    for root in paths:
        if not root.exists():
            continue
        for tiny_path in sorted(root.rglob("*.tiny")):
            metadata = _load_metadata(tiny_path)
            fixtures.append(Fixture(name=tiny_path.stem, path=tiny_path, metadata=metadata))
    return fixtures


def _normalize(text: str, *, keep_stack_traces: bool) -> str:
    options = NormalizationOptions(keep_stack_traces=keep_stack_traces)
    return normalize_output(text, options)


def _capture_execution(func) -> tuple[str, str]:
    from contextlib import redirect_stderr, redirect_stdout
    from io import StringIO

    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        func()
    return stdout.getvalue(), stderr.getvalue()


def _format_tiny_error(source: str, err: Exception) -> str:
    if isinstance(err, TinyLangError):
        return _format_error_for_source(source, err)
    return str(err)


def _run_interpreter(source: str, module_path: pathlib.Path) -> BackendResult:
    result = BackendResult()
    try:
        output = compile_and_run(
            source,
            module_namespace=_module_namespace_for_path(module_path),
            module_path=module_path,
            stream_output=False,
        )
        result.stdout = output
    except Exception as exc:  # noqa: BLE001 - normalized into stderr output
        result.stderr = _format_tiny_error(source, exc)
        result.exit_code = 1
    return result


def _run_native(source: str, module_path: pathlib.Path) -> BackendResult:
    result = BackendResult()
    try:
        output = run_with_native_backend(
            source,
            module_namespace=_module_namespace_for_path(module_path),
            module_path=module_path,
        )
        result.stdout = output
    except Exception as exc:  # noqa: BLE001 - normalized into stderr output
        result.stderr = _format_tiny_error(source, exc)
        result.exit_code = 1
    return result


def _run_llvm(source: str) -> BackendResult:
    result = BackendResult()

    def _execute():
        run_with_llvm_jit(source)

    try:
        result.stdout, result.stderr = _capture_execution(_execute)
    except RuntimeError as exc:
        message = str(exc)
        if "llvmlite is not installed" in message or "llvmlite-load" in message:
            return BackendResult(skipped=True, skip_reason=message)
        result.stderr = message
        result.exit_code = 1
    except Exception as exc:  # noqa: BLE001 - normalized into stderr output
        result.stderr = _format_tiny_error(source, exc)
        result.exit_code = 1
    return result


def _run_c_backend(source: str, compiler: str) -> BackendResult:
    if shutil.which(compiler) is None:
        return BackendResult(skipped=True, skip_reason=f"compiler {compiler!r} not found on PATH")
    result = BackendResult()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = pathlib.Path(tmpdir) / ("tiny_program.exe" if os.name == "nt" else "tiny_program")
        try:
            compile_to_c_executable(source, output_path, compiler=compiler)
        except RuntimeError as exc:
            message = str(exc)
            result.stderr = message
            result.exit_code = 1
            return result
        except Exception as exc:  # noqa: BLE001 - normalized into stderr output
            result.stderr = _format_tiny_error(source, exc)
            result.exit_code = 1
            return result
        process = subprocess.run(
            [str(output_path)],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=30,
        )
        result.stdout = process.stdout
        result.stderr = process.stderr
        result.exit_code = process.returncode
    return result


def _render_diff(label: str, expected: str, actual: str) -> str:
    expected_lines = expected.splitlines()
    actual_lines = actual.splitlines()
    diff = difflib.unified_diff(
        expected_lines,
        actual_lines,
        fromfile=f"{label} (expected)",
        tofile=f"{label} (actual)",
        lineterm="",
    )
    return "\n".join(diff)


def _print_header(title: str) -> None:
    sys.stdout.write(f"\n== {title} ==\n")


def _check_expected(fixture: Fixture, backend: str, result: BackendResult) -> list[str]:
    """Agreement on a crash is not success; compare independent fixture oracles first."""
    if result.skipped:
        return []
    failures = []
    if result.exit_code != fixture.metadata.expected_exit_code:
        failures.append(f"{fixture.name}/{backend}: expected exit {fixture.metadata.expected_exit_code}, got {result.exit_code}")
    if fixture.metadata.error_contains and fixture.metadata.error_contains not in result.stderr:
        failures.append(f"{fixture.name}/{backend}: missing expected diagnostic {fixture.metadata.error_contains!r}")
    if not fixture.metadata.expected_exit_code and result.stderr:
        failures.append(f"{fixture.name}/{backend}: unexpected stderr: {result.stderr}")
    for stream in ("stdout", "stderr"):
        snapshot = fixture.path.with_suffix("." + stream)
        if snapshot.exists():
            # Snapshots are program output. Broad parity normalization could erase a defect.
            expected = snapshot.read_text(encoding="utf-8").replace("\r\n", "\n")
            actual = getattr(result, stream).replace("\r\n", "\n")
            if expected != actual:
                failures.append(_render_diff(f"{fixture.name}/{backend} {stream} oracle", expected, actual))
    return failures


def _iter_backends(requested: Iterable[str] | None) -> tuple[str, ...]:
    if requested:
        return tuple(dict.fromkeys(requested))
    return DEFAULT_BACKENDS


def _compare_backend(
    *,
    fixture: Fixture,
    baseline_name: str,
    baseline: BackendResult,
    candidate_name: str,
    candidate: BackendResult,
    keep_stack_traces: bool,
) -> list[str]:
    diffs: list[str] = []
    baseline_stdout = _normalize(baseline.stdout, keep_stack_traces=keep_stack_traces)
    baseline_stderr = _normalize(baseline.stderr, keep_stack_traces=keep_stack_traces)
    candidate_stdout = _normalize(candidate.stdout, keep_stack_traces=keep_stack_traces)
    candidate_stderr = _normalize(candidate.stderr, keep_stack_traces=keep_stack_traces)
    if baseline.exit_code != candidate.exit_code:
        diffs.append(
            f"{fixture.name}: exit code mismatch {candidate_name}={candidate.exit_code} vs "
            f"{baseline_name}={baseline.exit_code}"
        )
    if baseline_stdout != candidate_stdout:
        diffs.append(
            _render_diff(
                f"{fixture.name} stdout ({baseline_name} vs {candidate_name})",
                baseline_stdout,
                candidate_stdout,
            )
        )
    if baseline_stderr != candidate_stderr:
        diffs.append(
            _render_diff(
                f"{fixture.name} stderr ({baseline_name} vs {candidate_name})",
                baseline_stderr,
                candidate_stderr,
            )
        )
    return diffs


def _select_fixture_roots(paths: Sequence[str] | None) -> list[pathlib.Path]:
    if paths:
        return [pathlib.Path(path) for path in paths]
    parity_root = PROJECT_ROOT / "tests" / "parity"
    spec_root = PROJECT_ROOT / "tests" / "spec"
    if parity_root.exists() and list(parity_root.rglob("*.tiny")):
        return [parity_root]
    return [spec_root]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run cross-backend parity tests")
    parser.add_argument(
        "--fixtures",
        action="append",
        help="Fixture directory (repeatable). Defaults to tests/parity or tests/spec.",
    )
    parser.add_argument(
        "--backend",
        action="append",
        choices=DEFAULT_BACKENDS,
        help="Backend to run (repeatable). Defaults to all supported backends.",
    )
    parser.add_argument(
        "--compiler",
        default="cc",
        help="C compiler to invoke for the C backend (default: cc).",
    )
    parser.add_argument(
        "--keep-stack-traces",
        action="store_true",
        help="Keep stack traces in normalized output (default: strip).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail when a backend is unavailable instead of skipping it.",
    )

    args = parser.parse_args(argv)
    fixture_roots = _select_fixture_roots(args.fixtures)
    fixtures = _discover_fixtures(fixture_roots)
    if not fixtures:
        sys.stderr.write("No fixtures found.\n")
        return 1

    requested_backends = _iter_backends(args.backend)
    overall_failures: list[str] = []
    executed = 0

    for fixture in fixtures:
        source = fixture.path.read_text(encoding="utf-8")
        backend_list = tuple(b for b in requested_backends
                             if fixture.metadata.backends is None or b in fixture.metadata.backends)
        backend_list = tuple(b for b in backend_list if b not in fixture.metadata.skip_backends)
        if not backend_list:
            continue

        _print_header(f"Fixture {fixture.name}")
        results: dict[str, BackendResult] = {}
        module_path = fixture.path.resolve()
        for backend in backend_list:
            if backend == "interpreter":
                results[backend] = _run_interpreter(source, module_path)
            elif backend == "native":
                results[backend] = _run_native(source, module_path)
            elif backend == "llvm":
                results[backend] = _run_llvm(source)
            elif backend == "c":
                results[backend] = _run_c_backend(source, args.compiler)
            else:
                results[backend] = BackendResult(skipped=True, skip_reason="unsupported backend")

        for backend, result in results.items():
            if not result.skipped:
                executed += 1
                overall_failures.extend(_check_expected(fixture, backend, result))
            if result.skipped:
                msg = f"{fixture.name}: {backend} skipped ({result.skip_reason})"
                if args.strict:
                    overall_failures.append(msg)
                sys.stdout.write(msg + "\n")

        available = {name: res for name, res in results.items() if not res.skipped}
        if len(available) <= 1:
            continue

        baseline_name = "interpreter" if "interpreter" in available else next(iter(available))
        baseline = available[baseline_name]
        for name, result in available.items():
            if name == baseline_name:
                continue
            diffs = _compare_backend(
                fixture=fixture,
                baseline_name=baseline_name,
                baseline=baseline,
                candidate_name=name,
                candidate=result,
                keep_stack_traces=args.keep_stack_traces,
            )
            if diffs:
                overall_failures.extend(diffs)

    if not executed:
        overall_failures.append("No backend executed; no parity evidence was produced.")
    if overall_failures:
        _print_header("Parity failures")
        for failure in overall_failures:
            sys.stdout.write(failure + "\n")
        return 1
    sys.stdout.write("\nAll parity checks matched.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
