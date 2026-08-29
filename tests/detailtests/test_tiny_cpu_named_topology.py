"""Coordinate-independent contracts for every TinyCPU schematic page.

These checks intentionally mention only circuit, port, and component names.
Coordinates remain XML rendering details and are never part of an assertion.
"""

from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

from tiny_cpu_circuit import inspect_project, validate_named_topology


PROJECT = Path(__file__).parents[2] / "hardware" / "logisim" / "TinyCPU.circ"


def _attributes(element):
    return {item.get("name"): item.get("val") for item in element.findall("a")}


def test_every_schematic_page_has_a_named_topological_interface():
    """Every page exposes unique, named inputs and outputs, independent of layout."""

    root = ET.parse(PROJECT).getroot()
    pages = root.findall("circuit")
    assert pages
    for page in pages:
        pins = [item for item in page.findall("comp") if item.get("name") == "Pin"]
        labels = [_attributes(pin).get("label", "").strip() for pin in pins]
        assert labels and all(labels), f"{page.get('name')} has an unnamed port"
        duplicates = [name for name, count in Counter(labels).items() if count > 1]
        assert not duplicates, f"{page.get('name')} repeats ports {duplicates}"


def test_every_subcircuit_instance_has_a_stable_name():
    """Hierarchical components are addressed by labels rather than anchors."""

    root = ET.parse(PROJECT).getroot()
    page_names = {page.get("name") for page in root.findall("circuit")}
    for page in root.findall("circuit"):
        instances = [
            item for item in page.findall("comp") if item.get("name") in page_names
        ]
        for instance in instances:
            assert _attributes(instance).get("label", "").strip(), (
                f"{page.get('name')}.{instance.get('name')} has no stable label"
            )


def test_every_schematic_page_is_electrically_connected_by_named_report():
    """The named per-page reports contain no open ports or electrical conflicts."""

    reports = {report.name: report for report in inspect_project(PROJECT)}
    assert reports
    failures = {
        name: {
            "unconnected": report.unconnected,
            "routing": report.routing_conflicts,
            "widths": report.width_conflicts,
        }
        for name, report in reports.items()
        if not report.connected
    }
    assert not failures


def test_checkout_named_topology_contract_is_complete():
    assert validate_named_topology(PROJECT) == ()


def test_named_topology_rejects_a_disconnected_named_port(tmp_path):
    project = tmp_path / "broken.circ"
    tree = ET.parse(PROJECT)
    top = tree.getroot().find("circuit[@name='TinyCPUMain']")
    reset = next(
        pin for pin in top.findall("comp[@name='Pin']")
        if _attributes(pin).get("label") == "RESET"
    )
    reset_location = reset.get("loc")
    for wire in list(top.findall("wire")):
        if reset_location in {wire.get("from"), wire.get("to")}:
            top.remove(wire)
    tree.write(project, encoding="utf-8", xml_declaration=True)

    violations = validate_named_topology(project)

    assert any("TinyCPUMain: unconnected RESET@" in item for item in violations)
