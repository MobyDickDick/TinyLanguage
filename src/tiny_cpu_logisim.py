#!/usr/bin/env python3
"""Download and run the pinned Logisim-evolution TinyCPU load smoke test."""

from __future__ import annotations

import argparse
import hashlib
import json
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
from tiny_cpu_assembler import assemble
from tiny_cpu_machine import encode_program, rom_image


LOGISIM_VERSION = "4.1.0"
JAVA_VERSION = "21.0.8"
LOGISIM_URL = (
    "https://github.com/logisim-evolution/logisim-evolution/releases/download/"
    f"v{LOGISIM_VERSION}/logisim-evolution-{LOGISIM_VERSION}-all.jar"
)
DEFAULT_JAR = Path.home() / ".cache" / "tinylanguage" / Path(LOGISIM_URL).name
DEFAULT_PROJECT = Path("hardware/logisim/TinyCPU.circ")
DEFAULT_PROGRAM = Path("hardware/logisim/ap5_countdown.tcpu")
DEFAULT_MATRIX = Path("hardware/logisim/tinycpu-electrical-matrix-v1.json")
DEFAULT_MACHINE_FORMAT = Path("hardware/logisim/tinycpu-machine-v1.json")
DEFAULT_ACCEPTANCE_OUTPUT = Path("artifacts/tinycpu-ap12-acceptance")
EXPECTED_STICKY_ERRORS = {"OVF", "DIV0", "ADDR", "INV", "ILL", "INPUT"}

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


def verify_matrix_contract(matrix_path: Path, machine_format_path: Path) -> None:
    """Reject incomplete or stale AP-11 electrical coverage metadata."""
    try:
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        machine = json.loads(machine_format_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SmokeTestError(f"could not read TinyCPU electrical matrix: {exc}") from exc
    if matrix.get("schema_version") != 1:
        raise SmokeTestError("TinyCPU electrical matrix must use schema version 1")
    expected = {row["mnemonic"]: row["code"] for row in machine.get("opcodes", ())}
    covered: dict[str, int] = {}
    duplicates: set[str] = set()
    for family in matrix.get("opcode_families", ()):
        for row in family.get("opcodes", ()):
            mnemonic = row.get("mnemonic")
            if mnemonic in covered:
                duplicates.add(mnemonic)
            covered[mnemonic] = row.get("code")
    missing = sorted(set(expected) - set(covered))
    extra = sorted(set(covered) - set(expected))
    wrong = sorted(name for name in expected.keys() & covered.keys() if covered[name] != expected[name])
    if missing or extra or wrong or duplicates:
        details = []
        for label, values in (("missing", missing), ("extra", extra), ("wrong code", wrong), ("duplicate", sorted(duplicates))):
            if values:
                details.append(f"{label}: {', '.join(values)}")
        raise SmokeTestError("invalid electrical opcode coverage (" + "; ".join(details) + ")")
    errors = [row.get("flag") for row in matrix.get("sticky_errors", ())]
    if set(errors) != EXPECTED_STICKY_ERRORS or len(errors) != len(EXPECTED_STICKY_ERRORS):
        raise SmokeTestError("electrical matrix must cover each sticky error exactly once")


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


def _replace_program_rom(
    tree: ET.ElementTree, source: str, *, raw_words: tuple[int, ...] | None = None
) -> None:
    """Install an assembled fixture in the temporary FetchDecode ROM."""
    fetch = tree.getroot().find("circuit[@name='FetchDecode']")
    if fetch is None:
        raise SmokeTestError("TinyCPU project has no FetchDecode circuit")
    roms = fetch.findall("comp[@name='ROM']")
    if len(roms) != 1:
        raise SmokeTestError("FetchDecode must contain exactly one program ROM")
    contents = roms[0].find("a[@name='contents']")
    if contents is None:
        contents = ET.SubElement(roms[0], "a", name="contents")
    contents.text = rom_image(raw_words or encode_program(assemble(source)))


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


def trace_test(java: str, jar: Path, project: Path, program: Path, output: Path) -> str:
    """Clock the AP-5 harness, retain its raw pin table, and compare it to the VM."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("# Logisim AP-5 trace was requested but has not started.\n", encoding="utf-8")
    if not program.is_file():
        raise SmokeTestError(f"TinyCPU AP-5 program does not exist: {program}")
    try:
        tree = ET.parse(project)
        _autonomous_trace_project(tree)
        _replace_program_rom(tree, program.read_text(encoding="utf-8"))
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
    return _tty_trace_to_tsv(result.stdout)


def matrix_test(java: str, jar: Path, project: Path, matrix_path: Path, output: Path) -> None:
    """Execute every declared AP-11 fixture with a replaced ROM and VM oracle."""
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    fixtures = matrix.get("fixtures", [])
    declared = {family["id"] for family in matrix.get("opcode_families", [])}
    declared.update(row["fixture"] for row in matrix.get("sticky_errors", []))
    supplied = {fixture.get("id") for fixture in fixtures}
    if supplied != declared or len(supplied) != len(fixtures):
        raise SmokeTestError("electrical matrix must define exactly one runnable fixture per family and error")
    output.mkdir(parents=True, exist_ok=True)
    for fixture in fixtures:
        fixture_id = fixture["id"]
        source = fixture.get("program", "")
        artifact = output / f"{fixture_id}.tsv"
        artifact.write_text("# fixture has not reached Logisim\n", encoding="utf-8")
        try:
            tree = ET.parse(project)
            _autonomous_trace_project(tree)
            raw_words = fixture.get("raw_words")
            _replace_program_rom(
                tree,
                source,
                raw_words=tuple(raw_words) if raw_words is not None else None,
            )
            with tempfile.TemporaryDirectory(prefix=f"tinycpu-{fixture_id}-") as directory:
                harness = Path(directory) / project.name
                tree.write(harness, encoding="UTF-8", xml_declaration=True)
                result = _run(
                    [java, "-jar", str(jar), "-tty", "table,halt", str(harness)],
                    stdout_path=artifact,
                )
        except (ET.ParseError, KeyError, ValueError) as exc:
            raise SmokeTestError(f"could not prepare electrical fixture {fixture_id}: {exc}") from exc
        # Reserved machine words have no symbolic VM instruction. Their
        # electrical contract is the ILL sticky bit followed by error halt.
        if fixture_id == "reserved-opcode":
            expected = {
                "schema_version": 1,
                "edges": [
                    {
                        "edge": 1,
                        "instruction": "RESERVED_63",
                        "boundary": {
                            "print_enable": False, "print_address_enable": False,
                            "print_value": 0, "print_valid": False,
                            "print_address_value": 0, "print_address_valid": False,
                            "halt_enable": False, "halt_error_enable": False,
                        },
                        "errors": ["ILL"], "halted": True,
                        "halted_with_error": True,
                    }
                ],
            }
        else:
            expected = capture_integration_trace(source)
        instructions = [edge["instruction"] for edge in expected["edges"]]
        try:
            observed = integration_trace_from_table(_tty_trace_to_tsv(result.stdout), instructions)
        except ValueError as exc:
            raise SmokeTestError(f"invalid Logisim table for {fixture_id}: {exc}") from exc
        mismatches = compare_trace(expected, observed)
        if mismatches:
            raise SmokeTestError(f"electrical fixture {fixture_id} mismatch: " + "; ".join(mismatches))
        print(f"AP-11 fixture {fixture_id} matches across {len(instructions)} clock edges")


def acceptance_test(
    java: str,
    jar: Path,
    project: Path,
    program: Path,
    matrix_path: Path,
    output: Path,
) -> None:
    """Run the mandatory AP-12 release gate and retain reproducibility evidence.

    Two independent simulator starts exercise the real RESET-at-start boundary.
    Comparing their normalized multi-cycle traces proves that resetting and
    restarting the maintained circuit produces the same 17-edge execution.
    The complete AP-11 matrix is then executed as part of the same command.
    """
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "acceptance.json"
    report_path.write_text(
        json.dumps({"schema_version": 1, "status": "started"}, indent=2) + "\n",
        encoding="utf-8",
    )
    runs = []
    for name in ("reset-start", "restart"):
        raw_path = output / f"{name}.tsv"
        normalized = trace_test(java, jar, project, program, raw_path)
        normalized_path = output / f"{name}.normalized.tsv"
        normalized_path.write_text(normalized, encoding="utf-8")
        runs.append(
            {
                "name": name,
                "raw_table": raw_path.name,
                "normalized_table": normalized_path.name,
                "sha256": hashlib.sha256(normalized.encode()).hexdigest(),
                "clock_edges": len(normalized.splitlines()) - 1,
            }
        )
    if runs[0]["sha256"] != runs[1]["sha256"]:
        raise SmokeTestError("AP-12 reset/restart traces are not reproducible")
    matrix_output = output / "isa-matrix"
    matrix_test(java, jar, project, matrix_path, matrix_output)
    fixture_count = len(json.loads(matrix_path.read_text(encoding="utf-8"))["fixtures"])
    report = {
        "schema_version": 1,
        "status": "passed",
        "logisim_version": LOGISIM_VERSION,
        "java_version": JAVA_VERSION,
        "reset_restart_runs": runs,
        "matrix": {"fixture_count": fixture_count, "directory": matrix_output.name},
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"AP-12 release acceptance passed with {fixture_count} electrical fixtures")


def main(argv: list[str] | None = None) -> int:
    """Run the pinned dependency and project-load checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", default="java", help="Java executable")
    parser.add_argument("--jar", type=Path, default=DEFAULT_JAR)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--program", type=Path, default=DEFAULT_PROGRAM)
    parser.add_argument("--trace-output", type=Path)
    parser.add_argument("--matrix-output", type=Path)
    parser.add_argument(
        "--acceptance-output",
        type=Path,
        help="run the mandatory AP-12 reset/restart, multi-cycle, and ISA release gate",
    )
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--machine-format", type=Path, default=DEFAULT_MACHINE_FORMAT)
    args = parser.parse_args(argv)
    if args.trace_output is not None:
        args.trace_output.parent.mkdir(parents=True, exist_ok=True)
        args.trace_output.write_text(
            "# TinyCPU Logisim trace gate has not reached the simulator.\n",
            encoding="utf-8",
        )
    try:
        verify_matrix_contract(args.matrix, args.machine_format)
        verify_java(args.java)
        obtain_jar(args.jar)
        smoke_test(args.java, args.jar, args.project)
        if args.trace_output is not None:
            trace_test(
                args.java, args.jar, args.project, args.program, args.trace_output
            )
        if args.matrix_output is not None:
            matrix_test(args.java, args.jar, args.project, args.matrix, args.matrix_output)
        if args.acceptance_output is not None:
            acceptance_test(
                args.java,
                args.jar,
                args.project,
                args.program,
                args.matrix,
                args.acceptance_output,
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
