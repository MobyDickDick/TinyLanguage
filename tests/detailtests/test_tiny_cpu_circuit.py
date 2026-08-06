import json
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

    assert not reports["TinyCPU"].connected
    assert "CLK@(80,140)" not in reports["TinyCPU"].unconnected
    assert "HALTED@(3300,100)" in reports["TinyCPU"].unconnected
    assert reports["Datapath"].components == 12
    assert reports["Datapath"].wires == 22
    for sheet in (
        "Datapath",
        "AddressPath",
        "Memory",
        "ErrorFlags",
        "FetchDecode",
        "FetchDecodeControls",
    ):
        assert reports[sheet].connected


def test_inspector_accepts_a_minimal_connected_project(tmp_path):
    project = tmp_path / "connected.circ"
    project.write_text(
        """<project><main name="main"/><circuit name="main">
        <comp lib="0" loc="(10,10)" name="Pin"><a name="label" val="A"/></comp>
        <comp lib="0" loc="(20,10)" name="Pin"><a name="label" val="B"/><a name="type" val="output"/></comp>
        <wire from="(10,10)" to="(20,10)"/>
        </circuit></project>""",
        encoding="utf-8",
    )

    report = inspect_project(project)[0]
    assert report.connected
    assert report.unconnected == ()
    assert main([str(project)]) == 0


def test_inspector_cli_rejects_incomplete_ap4_project(capsys):
    assert main([str(PROJECT)]) == 1
    output = capsys.readouterr().out
    assert "TinyCPU: INCOMPLETE" in output


def test_inspector_accepts_checked_in_diagnostic_projects():
    diagnostics = PROJECT.parent / "diagnostics"

    for project in sorted(diagnostics.glob("*.circ")):
        reports = inspect_project(project)
        assert reports
        assert all(report.connected for report in reports), project.name


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


def test_inspector_rejects_multiple_input_pins_on_one_net(tmp_path):
    project = tmp_path / "multi-driver.circ"
    project.write_text(
        """<project><main name="main"/><circuit name="main">
        <comp lib="0" loc="(10,10)" name="Pin"><a name="label" val="A"/></comp>
        <comp lib="0" loc="(20,10)" name="Pin"><a name="label" val="B"/></comp>
        <comp lib="0" loc="(30,10)" name="Pin"><a name="label" val="C"/><a name="type" val="output"/></comp>
        <wire from="(10,10)" to="(30,10)"/>
        </circuit></project>""",
        encoding="utf-8",
    )

    report = inspect_project(project)[0]
    assert not report.connected
    assert report.routing_conflicts == ("multiple input pins drive one net: A, B",)


def test_top_level_subcircuits_do_not_have_overlapping_anchors():
    report = next(item for item in inspect_project(PROJECT) if item.name == "TinyCPU")

    assert SUBCIRCUIT_ANCHOR_CLEARANCE == 200
    assert report.placement_conflicts == ()


def test_top_level_does_not_daisy_chain_unrelated_component_anchors():
    root = ET.parse(PROJECT).getroot()
    top = next(
        item for item in root.findall("circuit") if item.get("name") == "TinyCPU"
    )
    instance_locations = {
        component.get("loc")
        for component in top.findall("comp")
        if component.get("name") in {"Datapath", "AddressPath", "Memory", "ErrorFlags"}
    }

    for wire in top.findall("wire"):
        touched_instances = instance_locations & {wire.get("from"), wire.get("to")}
        assert len(touched_instances) <= 1


def test_inspector_rejects_overlapping_wire_segments(tmp_path):
    project = tmp_path / "overlapping-wires.circ"
    project.write_text(
        """<project><main name="main"/><circuit name="main">
        <comp lib="0" loc="(10,10)" name="Pin"/>
        <comp lib="0" loc="(40,10)" name="Pin"><a name="type" val="output"/></comp>
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
        <comp lib="0" loc="(40,20)" name="Pin"><a name="type" val="output"/></comp>
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
    source_circuits = {
        circuit.get("name"): circuit
        for circuit in ET.parse(PROJECT).getroot().findall("circuit")
    }

    assert {
        "TinyCPU-Datapath.circ",
        "TinyCPU-AddressPath.circ",
        "TinyCPU-Memory.circ",
        "TinyCPU-ErrorFlags.circ",
    } <= {path.name for path in written}
    for path in written:
        root = ET.parse(path).getroot()
        circuits = root.findall("circuit")
        assert len(circuits) == 1
        assert root.find("main").get("name") == circuits[0].get("name")
        source = source_circuits[circuits[0].get("name")]
        assert [component.get("loc") for component in circuits[0].findall("comp")] == [
            component.get("loc") for component in source.findall("comp")
        ]
        assert [
            (wire.get("from"), wire.get("to")) for wire in circuits[0].findall("wire")
        ] == [(wire.get("from"), wire.get("to")) for wire in source.findall("wire")]


def _leaf_circuit_signature(path):
    """Return the order-independent electrical content of a leaf project.

    Logisim does not assign meaning to the order of ``comp`` and ``wire`` XML
    elements.  Comparing their serialization made this regression dependent
    on checkout line endings and harmless editor reordering instead of the
    generated circuit.  A standalone sheet may also be translated as a whole
    when Logisim chooses a different drawing origin; that does not change its
    electrical content.  Keep every component attribute and nested ``a`` value
    in the signature, while treating components and undirected wires as
    multisets and normalizing their common origin.
    """

    root = ET.parse(path).getroot()
    circuit = root.find("circuit")
    assert circuit is not None

    def parse_location(value):
        x, y = value.strip("()").split(",")
        return int(x), int(y)

    locations = [
        parse_location(component.get("loc"))
        for component in circuit.findall("comp")
    ]
    locations.extend(
        parse_location(wire.get(endpoint))
        for wire in circuit.findall("wire")
        for endpoint in ("from", "to")
    )
    origin_x = min(x for x, _ in locations)
    origin_y = min(y for _, y in locations)

    def normalized_location(value):
        x, y = parse_location(value)
        return x - origin_x, y - origin_y

    def element_signature(element):
        return (
            element.tag,
            tuple(sorted(element.attrib.items())),
            (element.text or "").strip(),
            tuple(element_signature(child) for child in element),
        )

    def component_signature(component):
        return (
            component.get("name", ""),
            component.get("lib", ""),
            normalized_location(component.get("loc")),
            tuple(
                sorted(
                    (
                        attribute.get("name", ""),
                        attribute.get("val", ""),
                        attribute.text or "",
                    )
                    for attribute in component.findall("a")
                )
            ),
        )

    components = tuple(
        sorted(component_signature(component) for component in circuit.findall("comp"))
    )
    wires = tuple(
        sorted(
            tuple(
                sorted(
                    (
                        normalized_location(wire.get("from")),
                        normalized_location(wire.get("to")),
                    )
                )
            )
            for wire in circuit.findall("wire")
        )
    )
    circuit_attributes = tuple(
        sorted(
            (
                attribute.get("name", ""),
                attribute.get("val", ""),
                attribute.text or "",
            )
            for attribute in circuit.findall("a")
        )
    )
    return (
        element_signature(root.find("main")),
        tuple(
            element_signature(child)
            for child in root
            if child.tag not in {"main", "circuit"}
        ),
        circuit.get("name"),
        circuit_attributes,
        components,
        wires,
    )


def test_checked_in_diagnostic_projects_are_reproducible(tmp_path):
    written = split_leaf_circuits(PROJECT, tmp_path)
    diagnostics = PROJECT.parent / "diagnostics"

    assert {path.name for path in written} == {
        path.name for path in diagnostics.glob("*.circ")
    }
    for path in written:
        assert _leaf_circuit_signature(path) == _leaf_circuit_signature(
            diagnostics / path.name
        )


def test_leaf_signature_ignores_order_and_origin_but_detects_wire_changes(tmp_path):
    expected = PROJECT.parent / "diagnostics" / "TinyCPU-Datapath.circ"
    root = ET.parse(expected).getroot()
    circuit = root.find("circuit")
    assert circuit is not None

    components = circuit.findall("comp")
    wires = circuit.findall("wire")
    for child in components + wires:
        circuit.remove(child)
    circuit.extend(reversed(wires))
    circuit.extend(reversed(components))

    def translate(value):
        x, y = map(int, value.strip("()").split(","))
        return f"({x + 450},{y - 80})"

    for component in circuit.findall("comp"):
        component.set("loc", translate(component.get("loc")))
    for wire in circuit.findall("wire"):
        wire.set("from", translate(wire.get("from")))
        wire.set("to", translate(wire.get("to")))

    reordered = tmp_path / "reordered.circ"
    ET.ElementTree(root).write(reordered, encoding="utf-8", xml_declaration=True)
    assert _leaf_circuit_signature(reordered) == _leaf_circuit_signature(expected)

    circuit.find("wire").set("to", "(999,999)")
    changed = tmp_path / "changed.circ"
    ET.ElementTree(root).write(changed, encoding="utf-8", xml_declaration=True)
    assert _leaf_circuit_signature(changed) != _leaf_circuit_signature(expected)


def test_split_leaf_circuits_excludes_unknown_root_content(tmp_path):
    root = ET.parse(PROJECT).getroot()
    root.text = "\n--- ERROR ---\n"
    unexpected = ET.Element("unexpected")
    unexpected.text = "heap_get failed"
    root.insert(0, unexpected)
    contaminated = tmp_path / "contaminated.circ"
    ET.ElementTree(root).write(contaminated, encoding="utf-8", xml_declaration=True)

    output = tmp_path / "split"
    written = split_leaf_circuits(contaminated, output)
    assert written
    for path in written:
        data = path.read_bytes()
        assert b"--- ERROR ---" not in data
        assert b"heap_get failed" not in data
        standalone = ET.parse(path).getroot()
        assert standalone.find("unexpected") is None
        assert standalone.findall("lib")
        assert len(standalone.findall("circuit")) == 1


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


def test_inspector_flags_duplicate_components_as_possible_overlaid_circuit(tmp_path):
    project = tmp_path / "duplicate-components.circ"
    project.write_text(
        """<project><main name="main"/><circuit name="main">
        <comp lib="0" loc="(10,10)" name="Pin"><a name="label" val="A"/></comp>
        <comp lib="0" loc="(10,10)" name="Pin"><a name="label" val="A"/></comp>
        <comp lib="0" loc="(40,10)" name="Pin"><a name="label" val="B"/></comp>
        <wire from="(10,10)" to="(40,10)"/>
        </circuit></project>""",
        encoding="utf-8",
    )

    report = inspect_project(project)[0]

    assert not report.connected
    assert "multiple components share (10,10): A, A" in report.placement_conflicts
    assert (
        "possible overlaid circuit: 2 identical A components at (10,10)"
        in report.placement_conflicts
    )


def test_inspector_rejects_output_pin_connected_only_to_stub(tmp_path):
    project = tmp_path / "output-stub.circ"
    project.write_text(
        """<project><main name="main"/><circuit name="main">
        <comp lib="0" loc="(10,10)" name="Pin"><a name="label" val="OUT"/><a name="type" val="output"/></comp>
        <wire from="(10,10)" to="(40,10)"/>
        </circuit></project>""",
        encoding="utf-8",
    )

    report = inspect_project(project)[0]

    assert not report.connected
    assert report.unconnected == ("OUT@(10,10)",)


def test_inspector_rejects_input_pin_connected_only_to_stub(tmp_path):
    project = tmp_path / "input-stub.circ"
    project.write_text(
        """<project><main name="main"/><circuit name="main">
        <comp lib="0" loc="(10,10)" name="Pin"><a name="label" val="IN"/></comp>
        <wire from="(10,10)" to="(40,10)"/>
        </circuit></project>""",
        encoding="utf-8",
    )

    report = inspect_project(project)[0]

    assert not report.connected
    assert report.unconnected == ("IN@(10,10)",)


def test_inspector_rejects_incompatible_bus_widths(tmp_path):
    project = tmp_path / "width-mismatch.circ"
    project.write_text(
        """<project><main name="main"/><circuit name="main">
        <comp lib="0" loc="(10,10)" name="Pin"><a name="label" val="WORD"/><a name="width" val="16"/></comp>
        <comp lib="0" loc="(40,10)" name="Pin"><a name="label" val="BIT"/><a name="type" val="output"/></comp>
        <wire from="(10,10)" to="(40,10)"/>
        </circuit></project>""",
        encoding="utf-8",
    )

    report = inspect_project(project)[0]

    assert not report.connected
    assert report.width_conflicts == (
        "incompatible bus widths on one net: BIT@(40,10):1, WORD@(10,10):16",
    )


def test_hardware_contract_pin_direction_rules_are_profile_driven(tmp_path):
    project = tmp_path / "generic-direction.circ"
    project.write_text(
        """<project><main name="Generic"/><circuit name="Generic">
        <comp lib="0" loc="(10,10)" name="Pin"><a name="label" val="LIMIT"/><a name="type" val="output"/></comp>
        </circuit></project>""",
        encoding="utf-8",
    )
    profile = tmp_path / "generic-profile.json"
    profile.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "generic",
                "top_circuit": "Generic",
                "registers": {},
                "rams": {},
                "datapaths": {"Generic": {"pins": {"LIMIT": 1}}},
                "pin_directions": {"Generic": {"LIMIT": "input"}},
            }
        ),
        encoding="utf-8",
    )

    violations = validate_hardware_contract(project, profile)

    assert "Generic.LIMIT: pin type is output, expected input" in violations
