#!/usr/bin/env python3
"""Download and run the pinned Logisim-evolution TinyCPU load smoke test."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
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
MINIMUM_JAVA_FEATURE = 21
# Acceptance bundles record the supported runtime contract, not the local
# patch release. This keeps retained evidence reproducible across Java updates.
JAVA_VERSION = "21+"
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
    ("PRINT_ADDRESS_VALID", 1),
    ("PRINT_ADDRESS_VALUE", 16),
    ("PRINT_VALID", 1),
    ("PRINT_VALUE", 16),
    ("ERROR_OVF", 1),
    ("ERROR_DIV0", 1),
    ("ERROR_ADDR", 1),
    ("ERROR_INV", 1),
    ("ERROR_ILL", 1),
    ("ERROR_INPUT", 1),
    ("PRINT_ENABLE", 1),
    ("PRINT_ADDRESS_ENABLE", 1),
    ("HALTED", 1),
    ("HALTED_WITH_ERROR", 1),
    ("TRACE_PC", 12),
    ("TRACE_OPCODE", 22),
    ("TRACE_CLK", 1),
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
        stderr_lines = result.stderr.splitlines(keepends=True)
        halt_marker = "TtyInterface - halted due to halt pin"
        expected_halt = result.returncode == 0 and any(halt_marker in line for line in stderr_lines)
        if expected_halt:
            stderr_lines = [line for line in stderr_lines if halt_marker not in line]
            print("Logisim tty stopped at the configured halt pin.")
        if stderr_lines:
            print("".join(stderr_lines), end="", file=sys.stderr)
    if result.returncode:
        raise SmokeTestError(
            f"command exited with status {result.returncode}: {' '.join(command)}"
        )
    return result


def verify_java(java: str) -> None:
    """Require a Java runtime new enough for the pinned Logisim release."""
    result = _run([java, "-version"])
    output = f"{result.stdout}\n{result.stderr}"
    match = re.search(r'version "([^"+]+)', output)
    found = match.group(1) if match else "unknown"
    try:
        feature = int(found.split(".", 1)[0])
    except ValueError:
        feature = 0
    if feature < MINIMUM_JAVA_FEATURE:
        raise SmokeTestError(
            f"Java {MINIMUM_JAVA_FEATURE} or newer is required; found {found}"
        )


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
    if matrix.get("schema_version") != 2:
        raise SmokeTestError("TinyCPU electrical matrix must use schema version 2")
    expected = {row["mnemonic"]: row["code"] for row in machine.get("opcodes", ())}
    cases = matrix.get("opcode_cases", ())
    covered = {case.get("opcode") for case in cases}
    missing = sorted(set(expected) - covered)
    extra = sorted(covered - set(expected), key=str)
    duplicate_ids = len({case.get("id") for case in cases}) != len(cases)
    malformed = []
    for case in cases:
        opcode = case.get("opcode")
        try:
            instructions = assemble(case.get("program", ""))
        except (TypeError, ValueError) as exc:
            raise SmokeTestError(f"invalid behavioral case {case.get('id')}: {exc}") from exc
        if opcode not in {instruction.opcode for instruction in instructions.instructions}:
            malformed.append(str(case.get("id")))
    variants = {
        opcode: {case.get("variant") for case in cases if case.get("opcode") == opcode}
        for opcode in ("JUMP_ZERO", "JUMP_NOT_ZERO", "JUMP_NEGATIVE", "JUMP_ERROR", "JUMP_NOT_ERROR")
    }
    wrong_variants = sorted(opcode for opcode, values in variants.items() if values != {"taken", "not-taken"})
    if missing or extra or duplicate_ids or malformed or wrong_variants:
        details = []
        for label, values in (("missing", missing), ("extra", extra), ("case does not execute opcode", malformed), ("missing branch variant", wrong_variants)):
            if values:
                details.append(f"{label}: {', '.join(values)}")
        if duplicate_ids:
            details.append("duplicate case id")
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
    output_locations = {
        _pin_attributes(component).get("label"): component.get("loc")
        for component in circuit.findall("comp[@name='Pin']")
        if _pin_attributes(component).get("type") == "output"
    }
    # Minimal unit-test fixtures predate explicit output pins; production
    # projects resolve the maintained locations by label so a redraw cannot
    # leave the temporary logger attached to an empty coordinate.
    halted = output_locations.get("HALTED", "(3510,1540)")
    halted_with_error = output_locations.get("HALTED_WITH_ERROR", "(3510,1560)")
    wires = circuit.findall("wire")

    def connected_wire_contact(location: str, signal: str) -> str:
        """Return a maintained wire contact adjacent to a component terminal."""

        contacts = [
            wire.get("to") if wire.get("from") == location else wire.get("from")
            for wire in wires
            if location in {wire.get("from"), wire.get("to")}
        ]
        contacts = [contact for contact in contacts if contact is not None]
        if len(contacts) != 1:
            raise SmokeTestError(
                f"TinyCPUMain {signal} terminal {location} must have exactly one "
                f"adjacent wire contact, found {len(contacts)}"
            )
        return contacts[0]

    clock_pin = next(
        (
            component
            for component in circuit.findall("comp[@name='Pin']")
            if _pin_attributes(component).get("label") == "CLK"
        ),
        None,
    )
    if clock_pin is None or clock_pin.get("loc") is None:
        raise SmokeTestError("TinyCPUMain has no CLK input pin")
    clock_probe = connected_wire_contact(clock_pin.get("loc", ""), "CLK")

    opcode_splitter = next(
        (
            component
            for component in circuit.findall("comp[@name='Splitter']")
            if _pin_attributes(component).get("incoming") == "22"
        ),
        None,
    )
    if opcode_splitter is None or opcode_splitter.get("loc") is None:
        raise SmokeTestError("TinyCPUMain has no 22-bit opcode splitter")
    opcode_probe = opcode_splitter.get("loc", "")
    wire_contacts = {
        point for wire in wires for point in (wire.get("from"), wire.get("to"))
    }
    if opcode_probe not in wire_contacts:
        raise SmokeTestError(
            f"TinyCPUMain opcode splitter terminal {opcode_probe} is not a wire contact"
        )
    pc_probe = "(890,390)"
    if pc_probe not in wire_contacts:
        raise SmokeTestError(
            f"TinyCPUMain program-counter terminal {pc_probe} is not a wire contact"
        )
    # A constant-low RESET leaves every validity register in its power-up state.
    # That happened to produce a very large, almost entirely zero tty table: the
    # clock was running, but the processor had never been initialized and could
    # therefore never reach the generated halt pin.  PowerOnReset supplies the
    # one startup assertion expected by the maintained synchronous reset nets.
    for label, replacement in (("CLK", "Clock"), ("RESET", "PowerOnReset")):
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
        if replacement != "Clock":
            # PowerOnReset has no configurable attributes.  In particular, the
            # input Pin's label/type attributes were removed above so tty does
            # not continue to treat RESET as an undriven external input.
            continue
        for name, value in (("highDuration", "1"), ("lowDuration", "1"), ("phase", "0")):
            ET.SubElement(pin, "a", name=name, val=value)

    for location, label, width in (
        ("(3560,1860)", "TRACE_PC", 12),
        ("(3560,1880)", "TRACE_OPCODE", 22),
        ("(3560,1900)", "TRACE_CLK", 1),
        ("(3560,1920)", "halt", 1),
    ):
        pin = ET.SubElement(circuit, "comp", lib="0", loc=location, name="Pin")
        for name, value in (
            ("appearance", "classic"),
            ("facing", "west"),
            ("label", label),
            ("type", "output"),
        ):
            ET.SubElement(pin, "a", name=name, val=value)
        if width != 1:
            ET.SubElement(pin, "a", name="width", val=str(width))
    for location, label, width in (
        (pc_probe, "AP5_TRACE_PC", 12),
        ("(3480,1860)", "AP5_TRACE_PC", 12),
        (opcode_probe, "AP5_TRACE_OPCODE", 22),
        ("(3480,1880)", "AP5_TRACE_OPCODE", 22),
    ):
        tunnel = ET.SubElement(circuit, "comp", lib="0", loc=location, name="Tunnel")
        ET.SubElement(tunnel, "a", name="label", val=label)
        ET.SubElement(tunnel, "a", name="width", val=str(width))
    ET.SubElement(circuit, "wire", **{"from": "(3480,1860)", "to": "(3560,1860)"})
    ET.SubElement(circuit, "wire", **{"from": "(3480,1880)", "to": "(3560,1880)"})
    for location in (clock_probe, "(3480,1900)"):
        tunnel = ET.SubElement(circuit, "comp", lib="0", loc=location, name="Tunnel")
        ET.SubElement(tunnel, "a", name="label", val="AP5_TRACE_CLOCK")
    ET.SubElement(circuit, "wire", **{"from": "(3480,1900)", "to": "(3560,1900)"})
    # Stop tty mode for both successful and error termination.  Watching only
    # HALTED leaves Logisim clocking forever when the circuit correctly reports
    # HALTED_WITH_ERROR, hiding the actual electrical mismatch behind a timeout.
    gate = ET.SubElement(circuit, "comp", lib="1", loc="(3520,1920)", name="OR Gate")
    ET.SubElement(gate, "a", name="label", val="HALT_ANY")
    # Do not extend the two adjacent output nets down to the OR gate with
    # vertical wires.  Such a route necessarily crosses the lower halt net at
    # a wire endpoint and electrically shorts normal and error halt together.
    # These tunnels exist only in the generated tty harness; the maintained
    # circuit continues to use direct, visible routes for both public outputs.
    for location, label in (
        (halted, "AP5_HALT_NORMAL"),
        ("(3470,1900)", "AP5_HALT_NORMAL"),
        (halted_with_error, "AP5_HALT_ERROR"),
        ("(3470,1940)", "AP5_HALT_ERROR"),
    ):
        tunnel = ET.SubElement(circuit, "comp", lib="0", loc=location, name="Tunnel")
        ET.SubElement(tunnel, "a", name="label", val=label)
    for start, end in (
        ("(3520,1920)", "(3560,1920)"),
    ):
        ET.SubElement(circuit, "wire", **{"from": start, "to": end})


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


def _four_state_hex(row: dict[str, str]) -> str:
    """Encode one observable Logisim state using two bits per electrical cell."""
    encoded = []
    symbols = {"0": "00", "1": "01", "U": "10", "E": "11", "X": "11"}
    for label, width in TTY_OUTPUTS:
        if label in {"TRACE_PC", "TRACE_CLK"}:
            continue
        value = row[label].upper()
        if width == 16 and value.isdigit():
            value = f"{int(value):016b}"
        if len(value) != width or any(cell not in symbols for cell in value):
            raise SmokeTestError(
                f"Logisim state cannot be encoded: {label}={row[label]}"
            )
        encoded.extend(symbols[cell] for cell in value)
    bits = "".join(encoded)
    return f"0x{int(bits, 2):0{(len(bits) + 3) // 4}X}"


def _tty_trace_to_tsv(
    raw: str, execution_map: dict[str, set[str]] | None = None
) -> str:
    """Convert Logisim's grouped, change-driven tty table into rising-edge rows."""
    decoded_rows: list[dict[str, str]] = []
    expected_tokens = sum((width + 3) // 4 if width > 1 else 1 for _label, width in TTY_OUTPUTS)
    for line in raw.splitlines():
        tokens = line.split()
        if len(tokens) != expected_tokens:
            continue
        row: dict[str, str] = {}
        offset = 0
        for label, width in TTY_OUTPUTS:
            count = (width + 3) // 4 if width > 1 else 1
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
    for index, row in enumerate(decoded_rows, start=1):
        opcode = row["TRACE_OPCODE"]
        if any(cell in opcode.upper() for cell in ("U", "E", "X")):
            raise SmokeTestError(
                f"Logisim fetch/decode is undefined at table row {index}: "
                f"TRACE_OPCODE={opcode}"
            )
        operation = int(opcode, 2) >> 16
        row["HALT_ENABLE"] = "1" if operation == 44 else "0"
        row["HALT_ERROR_ENABLE"] = "1" if operation == 45 else "0"
    edges: list[dict[str, str]] = []
    last_low: dict[str, str] | None = None
    for row in decoded_rows:
        if row["TRACE_CLK"] == "0":
            last_low = row
        elif last_low is not None:
            # A halt asserted by this rising edge stops tty mode immediately,
            # so no following low row exists. Preserve the terminal state
            # instead of the pre-edge sample in that one case.
            terminal = row["HALTED"] == "1" or row["HALTED_WITH_ERROR"] == "1"
            advanced = (row["TRACE_PC"], row["TRACE_OPCODE"]) != (
                last_low["TRACE_PC"], last_low["TRACE_OPCODE"]
            )
            if terminal and not advanced:
                edges.append(row)
            else:
                edges.append(last_low)
                if terminal:
                    edges.append(row)
            last_low = None
    if last_low is not None and last_low["HALTED"] == "1":
        edges.append(last_low)

    history = execution_map if execution_map is not None else {}
    for edge_number, row in enumerate(edges, start=1):
        if row["PRINT_ENABLE"] == "0":
            if not row["PRINT_VALUE"].isdigit():
                row["PRINT_VALUE"] = "0"
            if row["PRINT_VALID"] not in {"0", "1"}:
                row["PRINT_VALID"] = "0"
        if row["PRINT_ADDRESS_ENABLE"] == "0":
            if not row["PRINT_ADDRESS_VALUE"].isdigit():
                row["PRINT_ADDRESS_VALUE"] = "0"
            if row["PRINT_ADDRESS_VALID"] not in {"0", "1"}:
                row["PRINT_ADDRESS_VALID"] = "0"
        pc_bits = row["TRACE_PC"]
        if any(cell in pc_bits.upper() for cell in ("U", "E", "X")):
            raise SmokeTestError(
                f"Logisim program counter is undefined at clock edge {edge_number}: "
                f"TRACE_PC={pc_bits}"
            )
        pc_hex = f"0x{int(pc_bits, 2):03X}"
        state_hex = _four_state_hex(row)
        states_at_pc = history.setdefault(pc_hex, set())
        if state_hex in states_at_pc:
            raise SmokeTestError(
                f"Logisim execution loop detected at PC {pc_hex}: "
                f"electrical state {state_hex} was observed again"
            )
        states_at_pc.add(state_hex)

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
    normalized = _tty_trace_to_tsv(result.stdout)
    try:
        observed = integration_trace_from_table(normalized, instructions)
    except ValueError as exc:
        rows = list(csv.DictReader(normalized.splitlines(), delimiter="\t"))
        if rows and rows[-1].get("HALTED_WITH_ERROR") == "1":
            error_names = [
                name
                for name in sorted(EXPECTED_STICKY_ERRORS)
                if rows[-1].get(f"ERROR_{name}") == "1"
            ]
            errors = ", ".join(error_names) or "no sticky error flag"
            raise SmokeTestError(
                f"AP-5 circuit halted with error after {len(rows)} clock edges "
                f"({errors}); expected {len(instructions)} edges and a normal HALT"
            ) from exc
        if rows and rows[-1].get("HALTED") == "1" and len(rows) < len(instructions):
            partial = integration_trace_from_table(
                normalized, instructions[: len(rows)]
            )
            partial_expected = {
                **expected,
                "edges": expected["edges"][: len(rows)],
            }
            mismatches = compare_trace(partial_expected, partial)
            detail = f"; first mismatch: {mismatches[0]}" if mismatches else ""
            raise SmokeTestError(
                f"AP-5 circuit halted normally after {len(rows)} clock edges; "
                f"expected {len(instructions)}{detail}"
            ) from exc
        raise SmokeTestError(f"invalid Logisim AP-5 table: {exc}") from exc
    mismatches = compare_trace(expected, observed)
    if mismatches:
        raise SmokeTestError("AP-5 electrical trace mismatch: " + "; ".join(mismatches))
    print(f"AP-5 electrical trace matches across {len(instructions)} clock edges")
    return normalized


def matrix_test(java: str, jar: Path, project: Path, matrix_path: Path, output: Path) -> None:
    """Execute every declared AP-11 fixture with a replaced ROM and VM oracle."""
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    fixtures = [*matrix.get("opcode_cases", []), *matrix.get("fixtures", [])]
    declared = {case["id"] for case in matrix.get("opcode_cases", [])}
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
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    fixture_count = len(matrix["opcode_cases"]) + len(matrix["fixtures"])
    evidence = []
    for evidence_path in sorted(path for path in output.rglob("*") if path.is_file()):
        if evidence_path == report_path:
            continue
        evidence.append(
            {
                "path": evidence_path.relative_to(output).as_posix(),
                "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
                "size_bytes": evidence_path.stat().st_size,
            }
        )
    report = {
        "schema_version": 2,
        "status": "passed",
        "logisim_version": LOGISIM_VERSION,
        "java_version": JAVA_VERSION,
        "reset_restart_runs": runs,
        "matrix": {"fixture_count": fixture_count, "directory": matrix_output.name},
        "evidence": evidence,
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"AP-12 release acceptance passed with {fixture_count} electrical fixtures")


def verify_acceptance_bundle(output: Path) -> None:
    """Verify a downloaded AP-12 evidence bundle without simulator dependencies."""
    report_path = output / "acceptance.json"
    try:
        if not stat.S_ISREG(report_path.lstat().st_mode):
            raise SmokeTestError("AP-12 acceptance report is not a regular file")
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SmokeTestError(f"could not read AP-12 acceptance report: {exc}") from exc
    if not isinstance(report, dict):
        raise SmokeTestError("AP-12 acceptance report must be a JSON object")
    if report.get("schema_version") != 2 or report.get("status") != "passed":
        raise SmokeTestError("AP-12 acceptance report is not a passed schema-version-2 report")
    evidence = report.get("evidence")
    if not isinstance(evidence, list):
        raise SmokeTestError("AP-12 acceptance report has no evidence inventory")
    recorded_paths = []
    for item in evidence:
        if not isinstance(item, dict):
            raise SmokeTestError("AP-12 evidence inventory contains an invalid entry")
        path = item.get("path")
        digest = item.get("sha256")
        size = item.get("size_bytes")
        if not isinstance(path, str):
            raise SmokeTestError("AP-12 evidence inventory contains an invalid path")
        relative = PurePosixPath(path)
        if (
            not path
            or "\\" in path
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.as_posix() != path
        ):
            raise SmokeTestError(f"unsafe AP-12 evidence path: {path}")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise SmokeTestError(f"invalid AP-12 evidence size: {path}")
        if (
            not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            raise SmokeTestError(f"invalid AP-12 evidence digest: {path}")
        recorded_paths.append(path)
    if recorded_paths != sorted(set(recorded_paths)):
        raise SmokeTestError("AP-12 evidence inventory paths must be unique and sorted")
    # An inventory authenticates bytes, but these fields establish that those
    # bytes represent every mandatory part of the AP-12 release gate.
    if report.get("logisim_version") != LOGISIM_VERSION:
        raise SmokeTestError("AP-12 acceptance report has an invalid Logisim version")
    if report.get("java_version") != JAVA_VERSION:
        raise SmokeTestError("AP-12 acceptance report has an invalid Java version")
    runs = report.get("reset_restart_runs")
    if not isinstance(runs, list) or len(runs) != 2:
        raise SmokeTestError("AP-12 acceptance report must describe two reset/restart runs")
    inventory_by_path = {item["path"]: item for item in evidence}
    for run, expected_name in zip(runs, ("reset-start", "restart")):
        if not isinstance(run, dict) or run.get("name") != expected_name:
            raise SmokeTestError("AP-12 acceptance report has invalid reset/restart metadata")
        raw = run.get("raw_table")
        normalized = run.get("normalized_table")
        if raw != f"{expected_name}.tsv" or normalized != f"{expected_name}.normalized.tsv":
            raise SmokeTestError("AP-12 acceptance report has invalid reset/restart paths")
        if raw not in inventory_by_path or normalized not in inventory_by_path:
            raise SmokeTestError("AP-12 reset/restart evidence is missing from the inventory")
        if run.get("sha256") != inventory_by_path[normalized]["sha256"]:
            raise SmokeTestError("AP-12 normalized trace digest does not match the inventory")
        edges = run.get("clock_edges")
        if not isinstance(edges, int) or isinstance(edges, bool) or edges <= 0:
            raise SmokeTestError("AP-12 acceptance report has an invalid clock-edge count")
    if runs[0]["sha256"] != runs[1]["sha256"] or runs[0]["clock_edges"] != runs[1]["clock_edges"]:
        raise SmokeTestError("AP-12 reset/restart trace metadata is not reproducible")
    matrix = report.get("matrix")
    if not isinstance(matrix, dict) or matrix.get("directory") != "isa-matrix":
        raise SmokeTestError("AP-12 acceptance report has invalid matrix metadata")
    fixture_count = matrix.get("fixture_count")
    if not isinstance(fixture_count, int) or isinstance(fixture_count, bool) or fixture_count <= 0:
        raise SmokeTestError("AP-12 acceptance report has an invalid fixture count")
    matrix_paths = [path for path in recorded_paths if path.startswith("isa-matrix/")]
    if len(matrix_paths) != fixture_count or any(not path.endswith(".tsv") for path in matrix_paths):
        raise SmokeTestError("AP-12 matrix fixture count does not match the inventory")
    actual_paths = []
    for path in output.rglob("*"):
        if path == report_path:
            continue
        try:
            mode = path.lstat().st_mode
        except OSError as exc:
            raise SmokeTestError(f"could not inspect AP-12 evidence: {exc}") from exc
        if stat.S_ISLNK(mode):
            raise SmokeTestError(
                f"AP-12 evidence bundle contains a symbolic link: "
                f"{path.relative_to(output).as_posix()}"
            )
        if stat.S_ISREG(mode):
            actual_paths.append(path.relative_to(output).as_posix())
        elif not stat.S_ISDIR(mode):
            raise SmokeTestError(
                f"AP-12 evidence bundle contains a non-regular entry: "
                f"{path.relative_to(output).as_posix()}"
            )
    actual_paths.sort()
    if recorded_paths != actual_paths:
        raise SmokeTestError("AP-12 evidence inventory does not match bundle contents")
    for item in evidence:
        relative = Path(*PurePosixPath(item["path"]).parts)
        evidence_path = output / relative
        try:
            mode = evidence_path.lstat().st_mode
            if not stat.S_ISREG(mode):
                raise SmokeTestError(
                    f"AP-12 evidence is not a regular file: {item['path']}"
                )
            contents = evidence_path.read_bytes()
        except OSError as exc:
            raise SmokeTestError(
                f"could not read AP-12 evidence {item['path']}: {exc}"
            ) from exc
        if item.get("size_bytes") != len(contents):
            raise SmokeTestError(f"AP-12 evidence size mismatch: {item['path']}")
        if item.get("sha256") != hashlib.sha256(contents).hexdigest():
            raise SmokeTestError(f"AP-12 evidence digest mismatch: {item['path']}")
    print(f"AP-12 acceptance evidence verified ({len(evidence)} files)")


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
    parser.add_argument(
        "--verify-acceptance", type=Path,
        help="verify a retained AP-12 evidence bundle without Java or Logisim",
    )
    args = parser.parse_args(argv)
    if args.trace_output is not None:
        args.trace_output.parent.mkdir(parents=True, exist_ok=True)
        args.trace_output.write_text(
            "# TinyCPU Logisim trace gate has not reached the simulator.\n",
            encoding="utf-8",
        )
    try:
        if args.verify_acceptance is not None:
            verify_acceptance_bundle(args.verify_acceptance)
            return 0
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
        f"Java {MINIMUM_JAVA_FEATURE}+)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
