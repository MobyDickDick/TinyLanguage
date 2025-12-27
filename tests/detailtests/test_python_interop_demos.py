import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT / "src"))

from tiny_language import compile_and_run


def test_math_demo_runs_end_to_end():
    program = PROJECT_ROOT / "src_tiny" / "python_math_demo.tiny"
    output = compile_and_run(program.read_text())

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    assert lines[:5] == [
        "Square roots via Python math:",
        "9.0",  # sqrt(81)
        "12.0",  # sqrt(144)
        "tau constant from Python:",
        "6.283185307179586",
    ]
    assert lines[-2:] == ["isfinite(second root):", "true"]


def test_json_demo_round_trips_and_maps_list_entries():
    program = PROJECT_ROOT / "src_tiny" / "python_json_demo.tiny"
    output = compile_and_run(program.read_text())

    lines = [line for line in output.splitlines() if line]
    assert "CWD from Python os:" in lines[0]
    assert lines[1]
    assert lines[2:] == [
        "parsed ok flag:",
        "true",
        "middle number:",
        "2",
        "round-tripped JSON:",
        '{"ok": true, "numbers": [1, 2, 3]}',
    ]


def test_allowlist_violation_is_reported():
    source = """
    define math = Python.import_module("math", new["sqrt"]);
    print(math.sqrt(9));
    try {
      define ignored = Python.call("math", "sin", Null, { allow: new["sqrt"] });
      print(ignored);
    } catch(err) {
      print(err.message);
    }
    """

    output = compile_and_run(source)
    lines = [line for line in output.splitlines() if line]

    assert lines[0] == "3.0"
    assert any("[PYDENY] attribute sin not allowed" in line for line in lines[1:])


def test_python_call_requires_allowlist():
    source = """
    try {
      define ignored = Python.call("math", "sqrt", new[9]);
    } catch(err) {
      print(err.message);
    }
    """

    output = compile_and_run(source)
    lines = [line for line in output.splitlines() if line]

    assert any("[PYDENY] attribute sqrt not allowed" in line for line in lines)


def test_banned_python_modules_are_blocked():
    source = """
    try {
      define forbidden = Python.import_module("subprocess");
      print(forbidden);
    } catch(err) {
      print(err.message);
    }
    """

    output = compile_and_run(source)
    lines = [line for line in output.splitlines() if line]

    assert any("[PYSEC] module subprocess denied" in line for line in lines)


def test_python_call_honors_timeout_option():
    source = """
    try {
      define ignored = Python.call("time", "sleep", new[0.05], { allow: new["sleep"], timeout_ms: 1 });
    } catch(err) {
      print(err.message);
    }
    """

    output = compile_and_run(source)
    lines = [line for line in output.splitlines() if line]

    assert any("[PYTIMEOUT]" in line for line in lines)


def test_proxy_pipeline_demo_runs_end_to_end():
    program = PROJECT_ROOT / "src_tiny" / "python_proxy_pipeline_demo.tiny"
    output = compile_and_run(program.read_text())

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    assert lines == ["81.0", "/tmp/example.txt", '{"area": 12}']


def test_python_fn_demo_runs_end_to_end():
    program = PROJECT_ROOT / "src_tiny" / "python_fn_demo.tiny"
    output = compile_and_run(program.read_text())

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    assert lines == ["sqrt via Python.fn:", "9.0", "ceil via Python.fn:", "5"]
