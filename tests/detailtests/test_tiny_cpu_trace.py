import json
from pathlib import Path

from tiny_cpu_trace import capture_trace, compare_trace, main


FIXTURES = Path(__file__).parents[2] / "hardware" / "logisim"
PROGRAM = FIXTURES / "ap5_countdown.tcpu"
TRACE = FIXTURES / "ap5_countdown_trace.json"


def test_ap5_countdown_trace_matches_checked_in_clock_edges():
    expected = json.loads(TRACE.read_text(encoding="utf-8"))
    actual = capture_trace(
        PROGRAM.read_text(encoding="utf-8"), watched_addresses=(100, 101)
    )

    assert compare_trace(expected, actual) == ()
    assert len(actual["edges"]) == 17
    assert actual["edges"][-1]["outputs"] == [3, 2, 1]
    assert actual["edges"][-1]["halted"] is True
    assert actual["edges"][-1]["halted_with_error"] is False


def test_trace_comparison_identifies_edge_and_field():
    expected = capture_trace("LOAD_CONST(1)\nHALT()")
    observed = json.loads(json.dumps(expected))
    observed["edges"][0]["pc"] = 99

    assert compare_trace(expected, observed) == ("edge 1: pc differs",)


def test_trace_cli_checks_an_observed_fixture(capsys):
    assert main([str(PROGRAM), "--watch", "100", "--watch", "101", "--check", str(TRACE)]) == 0
    assert "17 clock edges" in capsys.readouterr().out
