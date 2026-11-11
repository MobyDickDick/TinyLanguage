#!/usr/bin/env python3
"""Execute contract examples and retain separate frontend/codegen/build/run evidence.

Run from the checkout with ``python -m tools.correctness_audit --report PATH``.
Each backend/case runs in a fresh worker; a missing compiler, timeout, compiler
failure or oracle mismatch cannot count as successful execution. No JIT or Tiny
runtime helpers are used to calculate the expected values.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict
from fractions import Fraction
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from tools.correctness_cases import BACKENDS, CASES

ROOT = Path(__file__).resolve().parents[1]


def source_identity():
    """Hash maintained inputs, including untracked work, using unambiguous Git paths."""
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "-co", "--exclude-standard"], cwd=ROOT,
    ).decode("utf-8").split("\0")
    return {path: hashlib.sha256((ROOT / path).read_bytes() if (ROOT / path).is_file()
                                else b"<missing>").hexdigest()
            for path in sorted(set(paths)) if path and path.split("/")[0] not in {"artifacts", "dist", "build"}}


def known_gap(case, backend, result):
    """Recognize narrow, documented failures without changing any correct oracle.

    This inventory is intentionally stricter than an xfail by feature name. A
    different failure, crash, timeout, missing tool or newly fixed behavior is
    not grandfathered. The report still says ``failed`` for every known gap.
    """
    if (result.get("timeout") or result.get("worker_failure") or result.get("unavailable")
            or not stage_evidence(result)):
        return None
    stage = result.get("failure_stage")
    output = result.get("stdout", "")
    diagnostic = result.get("diagnostic", "")
    code = result.get("exit_code")
    executed = not stage and code == 0 and not result.get("stderr")
    if case.name == "integer-boundary" and backend == "llvm" and executed:
        if output == "1\n-2147483648\n":
            return "AUD-002"
    if case.name == "literals" and executed:
        expected = {"native": "42\nTiny\ntrue\nfalse\nnull\n", "c": "42\nTiny\ntrue\nfalse\nnull\n",
                    "llvm": "42\nTiny\n1\n0\nNull\n"}.get(backend)
        if output == expected:
            return "AUD-003"
    if case.name == "short-circuit":
        if (backend in {"native", "c"} and executed and output == "unexpected\nunexpected\n7\n"):
            return "AUD-004"
        if backend == "llvm" and stage == "codegen" and "operator and not supported" in diagnostic:
            return "AUD-004"
    if backend == "llvm" and stage == "codegen":
        signatures = {"heap-length": ("AUD-005", "unknown function len"),
                      "operator": ("AUD-006", "unknown class"),
                      "heap-error-status": ("AUD-007", "field access on unknown class value")}
        if case.name in signatures:
            issue, signature = signatures[case.name]
            if signature in diagnostic:
                return issue
        if case.name == "operator" and diagnostic == "__field_get expects class value and field name literal":
            return "AUD-006"
        if case.name == "file-builtins" and "main.heap_set" in diagnostic and "unknown function" in diagnostic:
            return "AUD-008"
    if (case.name == "python-interop" and backend == "llvm" and stage == "compile"
            and "__py_import_module" in result.get("build", {}).get("stderr", "")
            and "__py_call" in result.get("build", {}).get("stderr", "")):
        return "AUD-009"
    if case.name == "division-error":
        if backend == "c" and executed and output == "inf\nunreachable\n":
            return "AUD-010"
    return None


def write_json(path, value):
    """Keep an incremental record even when an external compiler stalls."""
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def compare_output(actual: str, expected: str) -> bool:
    """Compare line structure and text exactly; decimal numbers as exact rationals.

    Only trailing line-ending differences are portable. Do not erase banners,
    timings, paths, unexpected lines, or convert bools into integers.
    """
    a, b = actual.splitlines(), expected.splitlines()
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x == y:
            continue
        try:
            if Fraction(x) == Fraction(y):
                continue
        except (ValueError, ZeroDivisionError):
            pass
        return False
    return True


def worker(case, backend, compiler, directory, result_path):
    """Run one route, recording completed stages before advancing to the next."""
    import tiny_language as tiny

    record = {"backend": backend, "stages": {}, "stdout": "", "stderr": "", "exit_code": None}
    stage = "frontend"
    vm = None
    out, err = StringIO(), StringIO()

    def completed(name):
        record["stages"][name] = "passed"
        write_json(result_path, record)

    try:
        with redirect_stdout(out), redirect_stderr(err):
            statements = tiny._parse_and_lint(case.source)
            completed("frontend")
            module_path = directory / "main.tiny"
            module_path.write_text(case.source, encoding="utf-8")
            (directory / "audit_helper.tiny").write_text("fn twice(n) { return n*2; }", encoding="utf-8")
            if backend == "interpreter":
                stage = "execute"
                tiny.compile_and_run(case.source, module_path=module_path,
                                     stream_output=True, copy_on_call=case.copy_on_call)
            elif backend == "native":
                stage = "codegen"
                program = tiny.NativeCodeGenerator(allow_heap=True, allow_match=True,
                                                   source=case.source).compile_program(statements)
                completed("codegen")
                stage = "execute"
                vm = tiny.NativeVM(module_resolver=tiny.NativeModuleResolver(),
                                   module_path=module_path, source=case.source)
                out.write(vm.run(program))
            else:
                stage = "codegen"
                generated = (tiny.compile_to_llvm_ir(case.source, module_path=module_path if case.file_context else None)
                             if backend == "llvm" else tiny.compile_to_c_source(case.source))
                source_path = directory / ("program.ll" if backend == "llvm" else "program.c")
                source_path.write_text(generated, encoding="utf-8")
                record["generated_sha256"] = hashlib.sha256(generated.encode()).hexdigest()
                completed("codegen")
                stage = "compile"
                compiler_path = shutil.which(compiler)
                if compiler_path is None:
                    record.update(unavailable=f"Compiler not on PATH: {compiler}")
                    write_json(result_path, record)
                    return
                executable = directory / ("program.exe" if os.name == "nt" else "program")
                command = [compiler_path, str(source_path)]
                if backend == "llvm":
                    entry = directory / "entry.c"
                    entry.write_text("extern int tiny_main(void); int main(void) { return tiny_main(); }", encoding="utf-8")
                    command.append(str(entry))
                elif sys.platform != "win32":
                    command.append("-lm")
                command.extend(["-o", str(executable)])
                build = subprocess.run(command, capture_output=True, text=True, timeout=45,
                                       stdin=subprocess.DEVNULL)
                record["build"] = {"command": command, "exit_code": build.returncode,
                                   "stdout": build.stdout, "stderr": build.stderr}
                if build.returncode:
                    raise RuntimeError("compiler rejected generated source")
                completed("compile")
                stage = "execute"
                record["executable_sha256"] = hashlib.sha256(executable.read_bytes()).hexdigest()
                record["execute_command"] = [str(executable)]
                run = subprocess.run([str(executable)], capture_output=True, text=True, timeout=10,
                                     stdin=subprocess.DEVNULL)
                record.update(stdout=run.stdout, stderr=run.stderr, exit_code=run.returncode)
                completed("execute")
                write_json(result_path, record)
                return
            record.update(stdout=out.getvalue(), stderr=err.getvalue(), exit_code=0)
            completed("execute")
    except Exception as exc:  # Audit failures must remain visible, including crashes in prototypes.
        record["stages"][stage] = "failed"
        record.update(stdout="".join(vm.output) if vm else out.getvalue(), stderr=err.getvalue(),
                      exit_code=1, exception=type(exc).__name__, diagnostic=str(exc), failure_stage=stage)
    write_json(result_path, record)


def assess(case, result):
    """A declared error is success only at the specified stage and with no later effects."""
    if result.get("unavailable"):
        return "unavailable"
    if result.get("timeout") or result.get("worker_failure"):
        return "failed"
    if not stage_evidence(result):
        return "failed"
    if case.error:
        diagnostic = result.get("diagnostic", "") + result.get("stdout", "") + result.get("stderr", "")
        failed_at = result.get("failure_stage", "execute")
        # Compiled runtimes may put diagnostics on stdout; no arbitrary output is ignored.
        output = result.get("stdout", "")
        effect_ok = not output or (len(output.splitlines()) == 1 and case.error in output)
        ok = (result.get("exit_code") == 1 and failed_at == case.error_stage
              and case.error in diagnostic and effect_ok)
    else:
        ok = (result.get("exit_code") == 0 and not result.get("failure_stage")
              and not result.get("stderr") and compare_output(result.get("stdout", ""), case.expected))
    return "passed" if ok else "failed"


def stage_evidence(result):
    """Successful output cannot substitute for missing generation/build/run stages."""
    backend = result.get("backend")
    if backend not in BACKENDS:
        return False
    stages = ["frontend"]
    if backend != "interpreter":
        stages.append("codegen")
    if backend in {"llvm", "c"}:
        stages.append("compile")
    stages.append("execute")
    expected = {}
    for stage in stages:
        failed = stage == result.get("failure_stage")
        expected[stage] = "failed" if failed else "passed"
        if failed:
            break
    return result.get("stages") == expected


def run_audit(backends=BACKENDS, compiler="clang", timeout=65, cases=CASES):
    """Execute the requested matrix; retain exclusions separately from passing checks."""
    results = []
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT / "src"), env.get("PYTHONPATH", "")])
    # The corpus sets its semantic modes explicitly; caller profile toggles cannot alter it.
    for key in ("TINYLANG_COPY_ON_CALL", "TINY_ASSERT_NO_HEAP_LEAKS", "TINY_LINT_HEAP"):
        env.pop(key, None)
    for case in cases:
        for backend in backends:
            record = {"case": case.name, "backend": backend, "features": case.features,
                      "oracle": asdict(case), "source_sha256": hashlib.sha256(case.source.encode()).hexdigest()}
            if backend not in case.backends:
                record.update(status="not_applicable", reason="Outside the documented backend subset or mode")
            else:
                with tempfile.TemporaryDirectory(prefix="tiny-audit-") as temporary:
                    directory = Path(temporary)
                    result_path = directory / "result.json"
                    command = [sys.executable, "-m", "tools.correctness_audit", "--worker", case.name,
                               backend, "--compiler", compiler, "--directory", str(directory)]
                    try:
                        child = subprocess.run(command, capture_output=True, text=True, env=env,
                                               timeout=timeout, stdin=subprocess.DEVNULL, cwd=ROOT)
                        detail = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
                        if child.returncode or not detail:
                            detail.update(worker_failure=child.stderr or "Worker produced no result")
                    except subprocess.TimeoutExpired:
                        detail = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
                        detail["timeout"] = True
                    record.update(detail)
                    record["status"] = assess(case, detail)
                    if record["status"] == "failed":
                        record["known_gap"] = known_gap(case, backend, detail)
            results.append(record)
            print(f"{case.name}/{backend}: {record['status']}", flush=True)
    return results


def validate_report(report, identity=None):
    """Reject stale evidence, empty/subset matrices, duplicates and altered outcomes."""
    errors = []
    current = source_identity() if identity is None else identity
    if report.get("files_sha256") != current or report.get("source_changed_during_run"):
        errors.append("Source identity differs from the audited inputs")
    digest = hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()
    if report.get("source_sha256") != digest:
        errors.append("Source digest differs from the input manifest")
    expected = {(case.name, backend) for case in CASES for backend in BACKENDS}
    results = report.get("results", [])
    counts = {status: sum(r.get("status") == status for r in results)
              for status in ("passed", "failed", "unavailable", "not_applicable")}
    if report.get("counts") != counts:
        errors.append("Summary counts differ from the individual outcomes")
    observed = [(r.get("case"), r.get("backend")) for r in results]
    if set(observed) != expected or len(observed) != len(expected):
        errors.append("Missing, duplicated or unexpected matrix entries")
    cases = {case.name: case for case in CASES}
    for record in results:
        case = cases.get(record.get("case"))
        if case is None:
            continue
        # JSON round-trip canonicalizes tuples to lists.
        oracle = json.loads(json.dumps(asdict(case)))
        if record.get("oracle") != oracle:
            errors.append(f"Altered oracle: {case.name}")
        backend = record.get("backend")
        status = "not_applicable" if backend not in case.backends else assess(case, record)
        gap = known_gap(case, backend, record) if status == "failed" else None
        if record.get("status") != status or record.get("known_gap") != gap:
            errors.append(f"Altered outcome: {case.name}/{backend}")
        if status == "unavailable" or (status == "failed" and not gap):
            errors.append(f"Unqualified result: {case.name}/{backend}")
    return errors


def main(argv=None):
    """Write a source-bound report and return failure for missing or incorrect evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("artifacts/correctness-audit/backend-results.json"))
    parser.add_argument("--backend", action="append", choices=BACKENDS)
    parser.add_argument("--compiler", default="clang")
    parser.add_argument("--case", action="append", choices=[case.name for case in CASES])
    parser.add_argument("--allow-known-gaps", action="store_true",
                        help="Allow only inventoried failure signatures; these remain failed in the report.")
    parser.add_argument("--verify", type=Path, help="Verify a complete report against current inputs and oracles.")
    parser.add_argument("--worker", nargs=2, metavar=("CASE", "BACKEND"), help=argparse.SUPPRESS)
    parser.add_argument("--directory", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.verify:
        errors = validate_report(json.loads(args.verify.read_text(encoding="utf-8")))
        for error in errors:
            print(error)
        if not errors:
            print("Source-bound complete audit verified; known gaps remain failures, not support evidence.")
        return int(bool(errors))
    if args.worker:
        case = next(case for case in CASES if case.name == args.worker[0])
        worker(case, args.worker[1], args.compiler, args.directory, args.directory / "result.json")
        return 0
    cases = tuple(case for case in CASES if not args.case or case.name in args.case)
    hashes = source_identity()
    results = run_audit(tuple(dict.fromkeys(args.backend or BACKENDS)), args.compiler, cases=cases)
    compiler = shutil.which(args.compiler)
    version = subprocess.run([compiler, "--version"], capture_output=True, text=True,
                             timeout=10).stdout if compiler else None
    report = {"schema": 1, "scope": "Local contract audit; not release/platform qualification",
              "python": sys.version, "platform": platform.platform(), "compiler": version,
              "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "source_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
              "source_changed_during_run": hashes != source_identity(),
              "files_sha256": hashes, "results": results,
              "counts": {status: sum(r["status"] == status for r in results)
                         for status in ("passed", "failed", "unavailable", "not_applicable")}}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.report, report)
    print(json.dumps(report["counts"]))
    return int(report["source_changed_during_run"] or any(
        r["status"] == "unavailable" or (r["status"] == "failed" and
        not (args.allow_known_gaps and r.get("known_gap"))) for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
