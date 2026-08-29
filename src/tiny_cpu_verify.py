"""Run the reproducibility checks for the completed TinyCPU hardware package.

The verifier intentionally uses the same public helpers as the individual
command-line tools.  It gives a fresh checkout one stable command that checks
the structural contract, generated ROM artifacts, embedded Logisim image, and
the clock-edge reference trace without requiring Logisim to be installed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from tiny_cpu_assembler import assemble
from tiny_cpu_circuit import validate_hardware_contract, validate_named_topology
from tiny_cpu_machine import encode_program, listing, rom_image
from tiny_cpu_release import validate_release_contract
from tiny_cpu_trace import capture_integration_trace, capture_trace, compare_trace


class VerificationError(ValueError):
    """Raised when a checked-in TinyCPU artifact is not reproducible."""


def _attributes(component: ET.Element) -> dict[str, str]:
    return {item.get("name", ""): item.get("val", "") for item in component}


def _embedded_rom(project: Path) -> str:
    root = ET.parse(project).getroot()
    fetch = next(c for c in root.findall("circuit") if c.get("name") == "FetchDecode")
    rom = next(
        c for c in fetch.findall("comp")
        if _attributes(c).get("label") == "INSTRUCTION_ROM"
    )
    contents = next(a for a in rom.findall("a") if a.get("name") == "contents")
    return (contents.text or "").strip()


def _rom_words(contents: str) -> tuple[int, ...]:
    """Return Logisim ROM words independent of zero-padding and wrapping."""

    tokens = contents.split()
    if tokens[:3] != ["addr/data:", "12", "22"]:
        raise VerificationError("unsupported Logisim ROM header")
    try:
        return tuple(int(token, 16) for token in tokens[3:])
    except ValueError as error:
        raise VerificationError("invalid hexadecimal word in Logisim ROM") from error


def _verify_electrical_attributes(project: Path) -> None:
    """Reject electrical settings that differ from the accepted configuration.

    Logisim omits attributes which equal component defaults when saving a
    project.  Validate the resulting effective values rather than requiring a
    particular XML serialization.  Labels are deliberately excluded because
    they are descriptive and do not affect the circuit electrically.
    """

    root = ET.parse(project).getroot()
    circuits = {circuit.get("name"): circuit for circuit in root.findall("circuit")}
    required = (
        ("FetchDecode", "PC_INCREMENT_ENABLE", "Constant", "value", "0x1"),
        ("FetchDecode", "PC_INCREMENT_ENABLE", "Constant", "width", "1"),
        ("FetchDecode", "PC_INCREMENT", "Constant", "value", "0x1"),
        ("FetchDecode", "PC_INCREMENT", "Constant", "width", "16"),
        ("FetchDecode", "PC_NEXT_SELECT", "Multiplexer", "width", "16"),
        ("FetchDecode", "PROGRAM_LIMIT_COMPARE", "Comparator", "width", "16"),
        ("Operations", "RESULT_DATA_SELECT", "Multiplexer", "width", "16"),
    )
    for circuit_name, label, component_name, attribute, expected in required:
        circuit = circuits.get(circuit_name)
        candidates = () if circuit is None else circuit.findall("comp")
        component = next(
            (
                item
                for item in candidates
                if item.get("name") == component_name
                and _attributes(item).get("label") == label
            ),
            None,
        )
        actual = None if component is None else _attributes(component).get(attribute)
        if actual is None and component_name == "Constant":
            actual = {"value": "0x1", "width": "1"}.get(attribute)
        if actual != expected:
            raise VerificationError(
                "electrical attributes: "
                f"{circuit_name}.{label} ({component_name}) requires "
                f"{attribute}={expected!r}, found {actual!r}"
            )


def verify_checkout(repository: Path) -> tuple[str, ...]:
    """Verify the checked-in hardware deliverables below *repository*.

    Return the names of completed checks.  A mismatch raises
    :class:`VerificationError` with the artifact or contract that failed.
    """

    hardware = repository / "hardware" / "logisim"
    project = hardware / "TinyCPU.circ"
    profile = hardware / "tinycpu-16-12.json"
    # Full electrical simulation remains Logisim-evolution's job.  This
    # checkout gate validates the reproducible hardware deliverables that can be
    # checked deterministically without launching the simulator: the profile
    # contract, generated ROM/listing parity, embedded ROM parity, and trace.
    violations = validate_hardware_contract(project, profile)
    if violations:
        raise VerificationError("hardware contract: " + "; ".join(violations))
    _verify_electrical_attributes(project)
    topology_violations = validate_named_topology(project)
    if topology_violations:
        raise VerificationError("named topology: " + "; ".join(topology_violations))

    source = (hardware / "ap5_countdown.tcpu").read_text(encoding="utf-8")
    program = assemble(source)
    words = encode_program(program)
    generated_rom = rom_image(words)
    generated_listing = listing(program, words)
    if (hardware / "ap5_countdown.rom").read_text(encoding="utf-8") != generated_rom:
        raise VerificationError("ap5_countdown.rom differs from encoder output")
    if (hardware / "ap5_countdown.lst").read_text(encoding="utf-8") != generated_listing:
        raise VerificationError("ap5_countdown.lst differs from encoder output")
    if _rom_words(_embedded_rom(project)) != _rom_words(generated_rom):
        raise VerificationError("Logisim ROM differs from encoder output")

    expected_trace = capture_trace(source, watched_addresses=(100, 101))
    checked_trace = json.loads(
        (hardware / "ap5_countdown_trace.json").read_text(encoding="utf-8")
    )
    mismatches = compare_trace(expected_trace, checked_trace)
    if mismatches:
        raise VerificationError("AP 5 trace: " + "; ".join(mismatches))
    integration_fixture = json.loads(
        (hardware / "tinycpu_integration_trace.json").read_text(encoding="utf-8")
    )
    for scenario in integration_fixture.get("scenarios", ()):
        expected = capture_integration_trace(scenario["program"])
        mismatches = compare_trace(expected, scenario["trace"])
        if mismatches:
            raise VerificationError(
                f"integration trace {scenario.get('name', '<unnamed>')}: "
                + "; ".join(mismatches)
            )
    # AP 13 extends the checkout gate without changing the stable AP-8 result
    # tuple below.  Keep this check after the AP-8 artifacts so focused fixture
    # tests still report the artifact mismatch they were constructed to expose
    # before the deliberately minimal fixture reaches the release boundary.
    validate_release_contract(repository)
    return (
        "hardware contract", "named topology", "electrical attributes", "ROM and listing",
        "embedded ROM", "17-edge trace", "integration boundary trace",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a TinyCPU checkout")
    parser.add_argument(
        "repository", nargs="?", type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the checkout containing this script)",
    )
    args = parser.parse_args(argv)
    try:
        checks = verify_checkout(args.repository.resolve())
    except (OSError, ValueError, ET.ParseError) as error:
        print(f"TinyCPU verification FAILED: {error}")
        return 1
    print("TinyCPU verification passed: " + ", ".join(checks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
