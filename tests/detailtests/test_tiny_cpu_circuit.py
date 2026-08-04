import xml.etree.ElementTree as ET
from pathlib import Path

from tiny_cpu_circuit import (
    inspect_project,
    main,
    split_leaf_circuits,
    validate_hardware_contract,
)


PROJECT = Path(__file__).parents[2] / "hardware" / "logisim" / "TinyCPU.circ"
PROFILE = PROJECT.with_name("tinycpu-16-12.json")


def test_inspector_exposes_completed_and_pending_sheets():
    reports = {report.name: report for report in inspect_project(PROJECT)}

    assert reports["TinyCPU"].connected
    assert reports["FetchDecode"].connected
    assert reports["Datapath"].components == 12
    assert reports["Datapath"].wires == 17
    assert reports["Datapath"].connected
    assert reports["AddressPath"].connected
    assert reports["Memory"].connected
    assert reports["ErrorFlags"].connected


def test_inspector_accepts_a_minimal_connected_project(tmp_path):
    project = tmp_path / "connected.circ"
    project.write_text(
        """<project><main name="main"/><circuit name="main">
        <comp lib="0" loc="(10,10)" name="Pin"><a name="label" val="A"/></comp>
        <comp lib="0" loc="(20,10)" name="Pin"><a name="label" val="B"/></comp>
        <wire from="(10,10)" to="(20,10)"/>
        </circuit></project>""",
        encoding="utf-8",
    )

    report = inspect_project(project)[0]
    assert report.connected
    assert report.unconnected == ()
    assert main([str(project)]) == 0


def test_inspector_cli_accepts_connected_ap4_project(capsys):
    assert main([str(PROJECT)]) == 0
    output = capsys.readouterr().out
    assert "Datapath: connected" in output
    assert "Memory: connected" in output
    assert "ErrorFlags: connected" in output
    assert "FetchDecode: connected" in output
    assert "TinyCPU: connected" in output


def test_split_leaf_circuits_produces_independent_projects(tmp_path):
    written = split_leaf_circuits(PROJECT, tmp_path)

    assert {path.name for path in written} == {
        "TinyCPU-FetchDecode.circ",
        "TinyCPU-Datapath.circ",
        "TinyCPU-AddressPath.circ",
        "TinyCPU-Memory.circ",
        "TinyCPU-ErrorFlags.circ",
    }
    for path in written:
        root = ET.parse(path).getroot()
        circuits = root.findall("circuit")
        assert len(circuits) == 1
        assert root.find("main").get("name") == circuits[0].get("name")
        assert inspect_project(path)[0].connected


def test_checked_in_diagnostic_projects_are_reproducible(tmp_path):
    written = split_leaf_circuits(PROJECT, tmp_path)
    diagnostics = PROJECT.parent / "diagnostics"

    for path in written:
        assert path.read_bytes() == (diagnostics / path.name).read_bytes()


def test_hardware_profile_matches_starter_contract(capsys):
    assert validate_hardware_contract(PROJECT, PROFILE) == ()
    assert main(["--profile", str(PROFILE), "--contract-only", str(PROJECT)]) == 0
    assert "contract" in capsys.readouterr().out


def test_hardware_profile_reports_width_drift(tmp_path):
    project = tmp_path / "wrong-width.circ"
    project.write_text(
        PROJECT.read_text(encoding="utf-8").replace(
            '<a name="width" val="16"/>', '<a name="width" val="8"/>'
        ),
        encoding="utf-8",
    )

    violations = validate_hardware_contract(project, PROFILE)
    assert "Datapath.ACC: width is 8, expected 16" in violations


def test_hardware_profile_requires_ap2_status_and_offset_interfaces(tmp_path):
    project = tmp_path / "missing-ap2-output.circ"
    project.write_text(
        PROJECT.read_text(encoding="utf-8").replace(
            '<a name="label" val="NEGATIVE"/>',
            '<a name="label" val="NEGATIVE_MISSING"/>',
        ),
        encoding="utf-8",
    )

    violations = validate_hardware_contract(project, PROFILE)
    assert "Datapath: missing pin NEGATIVE" in violations


def test_hardware_profile_requires_ap4_instruction_rom(tmp_path):
    project = tmp_path / "missing-rom.circ"
    project.write_text(
        PROJECT.read_text(encoding="utf-8").replace(
            '<a name="label" val="INSTRUCTION_ROM"/>',
            '<a name="label" val="MISSING_ROM"/>',
        ),
        encoding="utf-8",
    )

    violations = validate_hardware_contract(project, PROFILE)
    assert "FetchDecode: missing ROM INSTRUCTION_ROM" in violations
