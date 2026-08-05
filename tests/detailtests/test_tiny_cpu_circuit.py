import xml.etree.ElementTree as ET
from pathlib import Path

from tiny_cpu_circuit import (
    SUBCIRCUIT_ANCHOR_CLEARANCE,
    inspect_project,
    main,
    split_leaf_circuits,
    validate_hardware_contract,
)

PROJECT = Path(__file__).parents[2] / "hardware" / "logisim" / "TinyCPU.circ"
PROFILE = PROJECT.with_name("tinycpu-16-12.json")
SMOKE_PROJECTS = PROJECT.parent / "smoke"


def test_two_pin_smoke_projects_are_minimal_and_unambiguous():
    expected_widths = {
        "PinPair-1bit.circ": "1",
        "PinPair-12bit.circ": "12",
        "PinPair-16bit.circ": "16",
    }

    assert {path.name for path in SMOKE_PROJECTS.glob("*.circ")} == set(expected_widths)
    for filename, expected_width in expected_widths.items():
        root = ET.parse(SMOKE_PROJECTS / filename).getroot()
        circuits = root.findall("circuit")
        assert len(circuits) == 1
        circuit = circuits[0]
        assert root.find("main").get("name") == circuit.get("name")

        components = circuit.findall("comp")
        wires = circuit.findall("wire")
        assert len(components) == 2
        assert {component.get("name") for component in components} == {"Pin"}
        assert len(wires) == 1

        attributes = [
            {item.get("name"): item.get("val") for item in component.findall("a")}
            for component in components
        ]
        widths = {item.get("width", "1") for item in attributes}
        assert widths == {expected_width}
        assert sum(item.get("type", "input") == "input" for item in attributes) == 1
        assert sum(item.get("type") == "output" for item in attributes) == 1

        start = tuple(map(int, wires[0].get("from").strip("()").split(",")))
        end = tuple(map(int, wires[0].get("to").strip("()").split(",")))
        assert start[1] == end[1]
        assert {wires[0].get("from"), wires[0].get("to")} == {
            component.get("loc") for component in components
        }
        report = inspect_project(SMOKE_PROJECTS / filename)[0]
        assert report.connected


def test_inspector_exposes_completed_and_pending_sheets():
    reports = {report.name: report for report in inspect_project(PROJECT)}

    assert reports["TinyCPU"].connected
    assert reports["FetchDecode"].connected
    assert reports["Datapath"].components == 12
    assert reports["Datapath"].wires == 22
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


def test_inspector_rejects_fetch_decode_pins_on_wrong_decoder_lanes(tmp_path):
    project = tmp_path / "wrong-fetch-lane.circ"
    project.write_text(
        PROJECT.read_text(encoding="utf-8").replace(
            '<wire from="(600,1490)" to="(1000,1490)"/>',
            '<wire from="(610,1500)" to="(1000,1500)"/>'
            '<wire from="(1000,1500)" to="(1000,1490)"/>',
        ),
        encoding="utf-8",
    )

    report = next(
        item for item in inspect_project(project) if item.name == "FetchDecode"
    )
    assert not report.connected
    assert report.routing_conflicts == (
        "FetchDecode.SET_INPUT: output pin (1000,1490) is not wired to "
        "decoder lane 53 at (600,1490)",
    )


def test_inspector_rejects_fetch_decode_pins_with_only_a_dangling_stub(tmp_path):
    project = tmp_path / "dangling-fetch-lane.circ"
    project.write_text(
        PROJECT.read_text(encoding="utf-8").replace(
            '<wire from="(600,1490)" to="(1000,1490)"/>',
            '<wire from="(1000,1490)" to="(1020,1490)"/>',
        ),
        encoding="utf-8",
    )

    report = next(
        item for item in inspect_project(project) if item.name == "FetchDecode"
    )
    assert not report.connected
    assert report.routing_conflicts == (
        "FetchDecode.SET_INPUT: output pin (1000,1490) is not wired to "
        "decoder lane 53 at (600,1490)",
    )


def test_fetch_decode_lane_check_follows_moved_decoder_location(tmp_path):
    project = tmp_path / "moved-fetch-decoder.circ"
    project.write_text(
        """<project><main name="FetchDecode"/><circuit name="FetchDecode">
        <comp lib="2" loc="(100,50)" name="Decoder"><a name="select" val="6"/></comp>
        <comp lib="0" loc="(250,1440)" name="Pin"><a name="label" val="SET_INPUT"/><a name="type" val="output"/></comp>
        <wire from="(130,1440)" to="(250,1440)"/>
        </circuit></project>""",
        encoding="utf-8",
    )

    report = inspect_project(project)[0]

    assert report.routing_conflicts == ()


def test_fetch_decode_lane_check_rejects_stub_with_moved_decoder(tmp_path):
    project = tmp_path / "moved-fetch-decoder-stub.circ"
    project.write_text(
        """<project><main name="FetchDecode"/><circuit name="FetchDecode">
        <comp lib="2" loc="(100,50)" name="Decoder"><a name="select" val="6"/></comp>
        <comp lib="0" loc="(250,1440)" name="Pin"><a name="label" val="SET_INPUT"/><a name="type" val="output"/></comp>
        <wire from="(250,1440)" to="(270,1440)"/>
        </circuit></project>""",
        encoding="utf-8",
    )

    report = inspect_project(project)[0]

    assert report.routing_conflicts == (
        "FetchDecode.SET_INPUT: output pin (250,1440) is not wired to "
        "decoder lane 53 at (130,1440)",
    )


def test_inspector_rejects_pin_connected_only_to_a_wire_stub(tmp_path):
    project = tmp_path / "stub-only.circ"
    project.write_text(
        """<project><main name="main"/><circuit name="main">
        <comp lib="0" loc="(10,10)" name="Pin"><a name="label" val="A"/></comp>
        <wire from="(10,10)" to="(40,10)"/>
        </circuit></project>""",
        encoding="utf-8",
    )

    report = inspect_project(project)[0]
    assert not report.connected
    assert report.unconnected == ("A@(10,10)",)


def test_inspector_rejects_multiple_output_pins_on_one_net(tmp_path):
    project = tmp_path / "multi-driver.circ"
    project.write_text(
        """<project><main name="main"/><circuit name="main">
        <comp lib="0" loc="(10,10)" name="Pin"><a name="label" val="A"/><a name="type" val="output"/></comp>
        <comp lib="0" loc="(20,10)" name="Pin"><a name="label" val="B"/><a name="type" val="output"/></comp>
        <comp lib="0" loc="(30,10)" name="Pin"><a name="label" val="C"/></comp>
        <wire from="(10,10)" to="(30,10)"/>
        </circuit></project>""",
        encoding="utf-8",
    )

    report = inspect_project(project)[0]
    assert not report.connected
    assert report.routing_conflicts == ("multiple output pins drive one net: A, B",)


def test_top_level_subcircuits_have_exclusive_routing_lanes():
    report = next(item for item in inspect_project(PROJECT) if item.name == "TinyCPU")

    assert SUBCIRCUIT_ANCHOR_CLEARANCE == 600
    assert report.placement_conflicts == ()


def test_top_level_does_not_daisy_chain_unrelated_component_anchors():
    root = ET.parse(PROJECT).getroot()
    top = next(
        item for item in root.findall("circuit") if item.get("name") == "TinyCPU"
    )
    instance_locations = {
        component.get("loc")
        for component in top.findall("comp")
        if component.get("name")
        in {"FetchDecode", "Datapath", "AddressPath", "Memory", "ErrorFlags"}
    }

    for wire in top.findall("wire"):
        touched_instances = instance_locations & {wire.get("from"), wire.get("to")}
        assert len(touched_instances) <= 1


def test_inspector_rejects_overlapping_subcircuit_symbols(tmp_path):
    project = tmp_path / "overlap.circ"
    project.write_text(
        PROJECT.read_text(encoding="utf-8").replace(
            'loc="(900,100)" name="Datapath"',
            'loc="(310,100)" name="Datapath"',
        ),
        encoding="utf-8",
    )

    report = next(item for item in inspect_project(project) if item.name == "TinyCPU")
    assert not report.connected
    assert report.placement_conflicts == (
        "FetchDecode@(300,100) overlaps the reserved lane of Datapath@(310,100)",
    )


def test_inspector_rejects_overlapping_wire_segments(tmp_path):
    project = tmp_path / "overlapping-wires.circ"
    project.write_text(
        """<project><main name="main"/><circuit name="main">
        <comp lib="0" loc="(10,10)" name="Pin"/>
        <comp lib="0" loc="(40,10)" name="Pin"/>
        <wire from="(10,10)" to="(40,10)"/>
        <wire from="(20,10)" to="(30,10)"/>
        </circuit></project>""",
        encoding="utf-8",
    )

    report = inspect_project(project)[0]
    assert not report.connected
    assert report.routing_conflicts == ("(10,10)->(40,10) overlaps (20,10)->(30,10)",)


def test_inspector_rejects_diagonal_wire_segments(tmp_path):
    project = tmp_path / "diagonal-wire.circ"
    project.write_text(
        """<project><main name="main"/><circuit name="main">
        <comp lib="0" loc="(10,10)" name="Pin"/>
        <comp lib="0" loc="(40,20)" name="Pin"/>
        <wire from="(10,10)" to="(40,20)"/>
        </circuit></project>""",
        encoding="utf-8",
    )

    report = inspect_project(project)[0]
    assert not report.connected
    assert report.routing_conflicts == (
        "(10,10)->(40,20) is diagonal; Logisim wires must be horizontal or vertical",
    )


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


def test_fetch_decode_split_diagnostic_is_standalone_and_connected():
    project = (
        Path(__file__).parents[2]
        / "hardware"
        / "logisim"
        / "diagnostics"
        / "TinyCPU-FetchDecode.circ"
    )

    report = next(
        item for item in inspect_project(project) if item.name == "FetchDecode"
    )

    assert report.connected, report
