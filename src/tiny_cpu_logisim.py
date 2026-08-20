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

from tiny_cpu_trace import (
    INTEGRATION_TABLE_COLUMNS,
    capture_integration_trace,
    compare_trace,
    integration_trace_from_table,
)


LOGISIM_VERSION = "4.1.0"
JAVA_VERSION = "21.0.8"
LOGISIM_URL = (
    "https://github.com/logisim-evolution/logisim-evolution/releases/download/"
    f"v{LOGISIM_VERSION}/logisim-evolution-{LOGISIM_VERSION}-all.jar"
)
DEFAULT_JAR = Path.home() / ".cache" / "tinylanguage" / Path(LOGISIM_URL).name
DEFAULT_PROJECT = Path("hardware/logisim/TinyCPU.circ")
DEFAULT_PROGRAM = Path("hardware/logisim/ap5_countdown.tcpu")

TTY_OUTPUTS = (
    ("PRINT_VALID", 1),
    ("PRINT_VALUE", 16),
    ("PRINT_ADDRESS_VALID", 1),
    ("PRINT_ADDRESS_VALUE", 16),
    ("PRINT_ENABLE", 1),
    ("PRINT_ADDRESS_ENABLE", 1),
    ("HALT_ENABLE", 1),
    ("HALT_ERROR_ENABLE", 1),
    ("ERROR_OVF", 1),
    ("ERROR_DIV0", 1),
    ("ERROR_ADDR", 1),
    ("ERROR_INV", 1),
    ("ERROR_ILL", 1),
    ("ERROR_INPUT", 1),
    ("HALTED", 1),
    ("HALTED_WITH_ERROR", 1),
    ("TRACE_CLK", 1),
    ("halt", 1),
)


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


def _pin_attributes(component: ET.Element) -> dict[str, str]:
    return {attribute.get("name", ""): attribute.get("val", "") for attribute in component}


def _autonomous_trace_project(tree: ET.ElementTree) -> None:
    """Replace only the temporary copy's CLK/RESET pins and add tty controls."""
    root = tree.getroot()
    main = root.find("main")
    circuit = root.find("circuit[@name='TinyCPUMain']")
    if main is None or circuit is None:
        raise SmokeTestError("TinyCPU project has no TinyCPUMain circuit")
    main.set("name", "TinyCPUMain")
    for label, replacement in (("CLK", "Clock"), ("RESET", "Constant")):
        pin = next(
            (
                component
                for component in circuit.findall("comp[@name='Pin']")
                if _pin_attributes(component).get("label") == label
            ),
            None,
        )
        if pin is None:
            raise SmokeTestError(f"TinyCPUMain has no {label} input pin")
        pin.set("name", replacement)
        for attribute in list(pin):
            pin.remove(attribute)
        if replacement == "Clock":
            for name, value in (("highDuration", "1"), ("lowDuration", "1"), ("phase", "0")):
                ET.SubElement(pin, "a", name=name, val=value)
        else:
            ET.SubElement(pin, "a", name="value", val="0x0")

    for location, label in (("(3500,1900)", "TRACE_CLK"), ("(3500,1920)", "halt")):
        pin = ET.SubElement(circuit, "comp", lib="0", loc=location, name="Pin")
        for name, value in (
            ("appearance", "classic"),
            ("facing", "west"),
            ("label", label),
            ("type", "output"),
        ):
            ET.SubElement(pin, "a", name=name, val=value)
    for location in ("(330,300)", "(3480,1900)"):
        tunnel = ET.SubElement(circuit, "comp", lib="0", loc=location, name="Tunnel")
        ET.SubElement(tunnel, "a", name="label", val="AP5_TRACE_CLOCK")
    ET.SubElement(circuit, "wire", **{"from": "(3480,1900)", "to": "(3500,1900)"})
    ET.SubElement(circuit, "wire", **{"from": "(3400,1780)", "to": "(3460,1780)"})
    ET.SubElement(circuit, "wire", **{"from": "(3460,1780)", "to": "(3460,1920)"})
    ET.SubElement(circuit, "wire", **{"from": "(3460,1920)", "to": "(3500,1920)"})


def _tty_trace_to_tsv(raw: str) -> str:
    """Convert Logisim's grouped, change-driven tty table into rising-edge rows."""
    decoded_rows: list[dict[str, str]] = []
    expected_tokens = sum(4 if width == 16 else 1 for _label, width in TTY_OUTPUTS)
    for line in raw.splitlines():
        tokens = line.split()
        if len(tokens) != expected_tokens:
            continue
        row: dict[str, str] = {}
        offset = 0
        for label, width in TTY_OUTPUTS:
            count = 4 if width == 16 else 1
            cells = tokens[offset : offset + count]
            offset += count
            grouped = "".join(cells)
            if width == 16 and set(grouped) <= {"0", "1"}:
                row[label] = str(int(grouped, 2))
            else:
                row[label] = grouped
        if row["TRACE_CLK"] in {"0", "1"}:
            decoded_rows.append(row)
    if not decoded_rows:
        raise SmokeTestError("Logisim AP-5 tty output contains no clocked table rows")

    edges: list[dict[str, str]] = []
    last_low: dict[str, str] | None = None
    for row in decoded_rows:
        if row["TRACE_CLK"] == "0":
            last_low = row
        elif last_low is not None:
            edges.append(last_low)
            last_low = None
    if last_low is not None and last_low["HALTED"] == "1":
        edges.append(last_low)

    lines = ["\t".join(INTEGRATION_TABLE_COLUMNS)]
    lines.extend(
        "\t".join(row[column] for column in INTEGRATION_TABLE_COLUMNS) for row in edges
    )
    return "\n".join(lines) + "\n"


def trace_test(java: str, jar: Path, project: Path, program: Path, output: Path) -> None:
    """Clock the AP-5 harness, retain its raw pin table, and compare it to the VM."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("# Logisim AP-5 trace was requested but has not started.\n", encoding="utf-8")
    if not program.is_file():
        raise SmokeTestError(f"TinyCPU AP-5 program does not exist: {program}")
    try:
        tree = ET.parse(project)
        _autonomous_trace_project(tree)
        with tempfile.TemporaryDirectory(prefix="tinycpu-logisim-") as directory:
            harness_project = Path(directory) / project.name
            tree.write(harness_project, encoding="UTF-8", xml_declaration=True)
            result = _run(
                [java, "-jar", str(jar), "-tty", "table,halt", str(harness_project)],
                stdout_path=output,
            )
    except ET.ParseError as exc:
        raise SmokeTestError(f"could not prepare AP-5 trace harness: {exc}") from exc

    expected = capture_integration_trace(program.read_text(encoding="utf-8"))
    instructions = [edge["instruction"] for edge in expected["edges"]]
    try:
        observed = integration_trace_from_table(_tty_trace_to_tsv(result.stdout), instructions)
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
