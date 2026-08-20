#!/usr/bin/env python3
"""Download and run the pinned Logisim-evolution TinyCPU load smoke test."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET

from tiny_cpu_trace import capture_integration_trace, compare_trace, integration_trace_from_table


LOGISIM_VERSION = "4.1.0"
JAVA_VERSION = "21.0.8"
LOGISIM_URL = (
    "https://github.com/logisim-evolution/logisim-evolution/releases/download/"
    f"v{LOGISIM_VERSION}/logisim-evolution-{LOGISIM_VERSION}-all.jar"
)
DEFAULT_JAR = Path.home() / ".cache" / "tinylanguage" / Path(LOGISIM_URL).name
DEFAULT_PROJECT = Path("hardware/logisim/TinyCPU.circ")
DEFAULT_PROGRAM = Path("hardware/logisim/ap5_countdown.tcpu")


class SmokeTestError(RuntimeError):
    """Report a reproducibility or simulator-load failure."""


def _run(
    command: list[str],
    *,
    timeout: int = 120,
    stdout_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command while retaining its complete diagnostics for CI logs."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        partial_stdout = exc.stdout or ""
        partial_stderr = exc.stderr or ""
        if isinstance(partial_stdout, bytes):
            partial_stdout = partial_stdout.decode(errors="replace")
        if isinstance(partial_stderr, bytes):
            partial_stderr = partial_stderr.decode(errors="replace")
        if partial_stdout:
            print(partial_stdout, end="")
        if partial_stderr:
            print(partial_stderr, end="", file=sys.stderr)
        if stdout_path is not None:
            stdout_path.parent.mkdir(parents=True, exist_ok=True)
            stdout_path.write_text(partial_stdout, encoding="utf-8")
        raise SmokeTestError(f"could not run {' '.join(command)}: {exc}") from exc
    except OSError as exc:
        raise SmokeTestError(f"could not run {' '.join(command)}: {exc}") from exc
    if result.stdout:
        print(result.stdout, end="")
    if stdout_path is not None:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text(result.stdout, encoding="utf-8")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode:
        raise SmokeTestError(
            f"command exited with status {result.returncode}: {' '.join(command)}"
        )
    return result


def verify_java(java: str) -> None:
    """Require the exact pinned Java feature/security version."""
    result = _run([java, "-version"])
    output = f"{result.stdout}\n{result.stderr}"
    match = re.search(r'version "([^"+]+)', output)
    if not match or match.group(1) != JAVA_VERSION:
        found = match.group(1) if match else "unknown"
        raise SmokeTestError(f"Java {JAVA_VERSION} is required; found {found}")


def obtain_jar(jar: Path) -> None:
    """Fetch the version-addressed upstream JAR when it is not cached."""
    if jar.is_file():
        return
    jar.parent.mkdir(parents=True, exist_ok=True)
    partial = jar.with_suffix(f"{jar.suffix}.part")
    print(f"Downloading Logisim-evolution {LOGISIM_VERSION} from {LOGISIM_URL}")
    try:
        urllib.request.urlretrieve(LOGISIM_URL, partial)
        partial.replace(jar)
    except Exception as exc:
        partial.unlink(missing_ok=True)
        raise SmokeTestError(f"could not download pinned Logisim-evolution: {exc}") from exc


def smoke_test(java: str, jar: Path, project: Path) -> None:
    """Print the simulator version, then load the maintained top-level circuit."""
    if not project.is_file():
        raise SmokeTestError(f"TinyCPU project does not exist: {project}")
    version = _run([java, "-jar", str(jar), "--version"])
    version_output = f"{version.stdout}\n{version.stderr}"
    if LOGISIM_VERSION not in version_output:
        raise SmokeTestError(
            f"expected Logisim-evolution {LOGISIM_VERSION} in version output"
        )
    _run(
        [
            java,
            "-jar",
            str(jar),
            "-tty",
            "table",
            str(project),
        ]
    )


def trace_test(java: str, jar: Path, project: Path, program: Path, output: Path) -> None:
    """Clock the AP-5 harness, retain its raw pin table, and compare it to the VM."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("# Logisim AP-5 trace was requested but has not started.\n", encoding="utf-8")
    if not program.is_file():
        raise SmokeTestError(f"TinyCPU AP-5 program does not exist: {program}")
    try:
        tree = ET.parse(project)
        main = tree.getroot().find("main")
        if main is None or tree.getroot().find("circuit[@name='AP5TraceHarness']") is None:
            raise SmokeTestError("TinyCPU project has no AP5TraceHarness circuit")
        main.set("name", "AP5TraceHarness")
        with tempfile.TemporaryDirectory(prefix="tinycpu-logisim-") as directory:
            harness_project = Path(directory) / project.name
            tree.write(harness_project, encoding="UTF-8", xml_declaration=True)
            result = _run(
                [java, "-jar", str(jar), "-tty", "table", str(harness_project)],
                stdout_path=output,
            )
    except ET.ParseError as exc:
        raise SmokeTestError(f"could not prepare AP-5 trace harness: {exc}") from exc

    expected = capture_integration_trace(program.read_text(encoding="utf-8"))
    instructions = [edge["instruction"] for edge in expected["edges"]]
    try:
        observed = integration_trace_from_table(result.stdout, instructions)
    except ValueError as exc:
        raise SmokeTestError(f"invalid Logisim AP-5 table: {exc}") from exc
    mismatches = compare_trace(expected, observed)
    if mismatches:
        raise SmokeTestError("AP-5 electrical trace mismatch: " + "; ".join(mismatches))
    print(f"AP-5 electrical trace matches across {len(instructions)} clock edges")


def main(argv: list[str] | None = None) -> int:
    """Run the pinned dependency and project-load checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", default="java", help="Java executable")
    parser.add_argument("--jar", type=Path, default=DEFAULT_JAR)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--program", type=Path, default=DEFAULT_PROGRAM)
    parser.add_argument("--trace-output", type=Path)
    args = parser.parse_args(argv)
    if args.trace_output is not None:
        args.trace_output.parent.mkdir(parents=True, exist_ok=True)
        args.trace_output.write_text(
            "# TinyCPU Logisim trace gate has not reached the simulator.\n",
            encoding="utf-8",
        )
    try:
        verify_java(args.java)
        obtain_jar(args.jar)
        smoke_test(args.java, args.jar, args.project)
        if args.trace_output is not None:
            trace_test(
                args.java, args.jar, args.project, args.program, args.trace_output
            )
    except SmokeTestError as exc:
        print(f"TinyCPU Logisim smoke test failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"TinyCPU Logisim smoke test passed (Logisim-evolution {LOGISIM_VERSION}, "
        f"Java {JAVA_VERSION})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
