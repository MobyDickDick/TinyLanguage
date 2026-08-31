import json
from pathlib import Path

from tiny_cpu_trace import (
    INTEGRATION_TABLE_COLUMNS,
    capture_integration_trace,
    capture_trace,
    compare_trace,
    integration_trace_from_table,
    main,
)


FIXTURES = Path(__file__).parents[2] / "hardware" / "logisim"
PROGRAM = FIXTURES / "ap5_countdown.tcpu"
TRACE = FIXTURES / "ap5_countdown_trace.json"
INTEGRATION_TRACE = FIXTURES / "tinycpu_integration_trace.json"


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

    assert compare_trace(expected, observed) == (
        "edge 1: pc differs (expected 1, observed 99)",
    )


def test_trace_cli_checks_an_observed_fixture(capsys):
    assert main([str(PROGRAM), "--watch", "100", "--watch", "101", "--check", str(TRACE)]) == 0
    assert "17 clock edges" in capsys.readouterr().out


def test_trace_cli_checks_an_exported_integration_boundary(tmp_path, capsys):
    program = tmp_path / "normal_halt.tcpu"
    observed = tmp_path / "logisim_trace.json"
    program.write_text("LOAD_CONST(7)\nPRINT()\nHALT()\n", encoding="utf-8")
    observed.write_text(
        json.dumps(capture_integration_trace(program.read_text(encoding="utf-8"))),
        encoding="utf-8",
    )

    assert main([str(program), "--integration", "--check", str(observed)]) == 0
    assert "3 clock edges" in capsys.readouterr().out


def _normal_halt_logisim_table() -> str:
    rows = [
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        (1, 0, 7, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        (0, 0, 7, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0),
    ]
    return "\t".join(INTEGRATION_TABLE_COLUMNS) + "\n" + "\n".join(
        "\t".join(map(str, row)) for row in rows
    )


def test_logisim_table_converts_flat_pin_rows_to_boundary_trace():
    expected = capture_integration_trace("LOAD_CONST(7)\nPRINT()\nHALT()\n")

    observed = integration_trace_from_table(
        _normal_halt_logisim_table(),
        ["LOAD_CONST", "PRINT", "HALT"],
    )

    assert compare_trace(expected, observed) == ()


def test_trace_cli_checks_a_logisim_table_export(tmp_path, capsys):
    program = tmp_path / "normal_halt.tcpu"
    table = tmp_path / "normal_halt.tsv"
    program.write_text("LOAD_CONST(7)\nPRINT()\nHALT()\n", encoding="utf-8")
    table.write_text(_normal_halt_logisim_table(), encoding="utf-8")

    assert main(
        [str(program), "--integration", "--check-logisim-table", str(table)]
    ) == 0
    assert "3 clock edges" in capsys.readouterr().out


def test_logisim_table_rejects_undefined_pin_values():
    table = _normal_halt_logisim_table().replace("0\t0\t0\t0", "x\t0\t0\t0", 1)

    try:
        integration_trace_from_table(table, ["LOAD_CONST", "PRINT", "HALT"])
    except ValueError as error:
        assert "must be a defined bit" in str(error)
    else:
        raise AssertionError("undefined electrical observations must not be accepted")


def test_trace_cli_rejects_memory_watches_for_boundary_mode(capsys):
    try:
        main([str(PROGRAM), "--integration", "--watch", "100"])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("argparse should reject incompatible trace modes")

    assert "--watch cannot be combined with --integration" in capsys.readouterr().err


def test_integration_trace_covers_the_three_top_level_outcomes():
    fixture = json.loads(INTEGRATION_TRACE.read_text(encoding="utf-8"))
    scenarios = {item["name"]: item for item in fixture["scenarios"]}
    assert set(scenarios) == {"normal_halt", "error_halt", "invalid_print"}

    for scenario in scenarios.values():
        assert compare_trace(
            capture_integration_trace(scenario["program"]), scenario["trace"]
        ) == ()

    normal = scenarios["normal_halt"]["trace"]["edges"][-1]["boundary"]
    error = scenarios["error_halt"]["trace"]["edges"][-1]["boundary"]
    invalid = scenarios["invalid_print"]["trace"]["edges"][0]
    assert normal["halt_enable"] and not normal["halt_error_enable"]
    assert error["halt_error_enable"] and not error["halt_enable"]
    assert invalid["boundary"]["print_enable"]
    assert not invalid["boundary"]["print_valid"]
    assert invalid["errors"] == ["INV"]
