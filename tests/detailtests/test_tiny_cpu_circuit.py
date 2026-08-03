from pathlib import Path

from tiny_cpu_circuit import inspect_project, main


PROJECT = Path(__file__).parents[2] / "hardware" / "logisim" / "TinyCPU.circ"


def test_inspector_exposes_unwired_starter_sheets():
    reports = {report.name: report for report in inspect_project(PROJECT)}

    assert reports["TinyCPU"].wires == 0
    assert reports["Datapath"].components == 8
    assert "ACC@(280,120)" in reports["Datapath"].unconnected
    assert not reports["Datapath"].connected


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


def test_inspector_cli_fails_for_incomplete_project(capsys):
    assert main([str(PROJECT)]) == 1
    output = capsys.readouterr().out
    assert "Datapath: INCOMPLETE" in output
    assert "0 wires" in output
