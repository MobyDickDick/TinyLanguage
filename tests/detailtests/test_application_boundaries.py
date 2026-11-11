"""Check application cleanup and document the actual Python trust boundary."""

from pathlib import Path
import json
import sys
import threading
from types import ModuleType

from tiny_language import Runtime, compile_and_run

ROOT = Path(__file__).resolve().parents[2]


def test_json_application_joins_worker_and_frees_heap(tmp_path, monkeypatch):
    """Run the maintained application fixture with a separate local dependency."""
    (tmp_path / "tiny.toml").write_text('[package]\nname="app"\nversion="1.0.0"\n')
    (tmp_path / "tiny.lock").write_text('[[dependencies]]\nname="pricing"\nversion="1.0.0"\n'
                                        'source="path"\npath="dependency"\n')
    dependency = tmp_path / "dependency/src"
    dependency.mkdir(parents=True)
    (dependency / "transform.tiny").write_text("fn apply(value) { return value * 2; }\n")
    input_file = tmp_path / "input.json"
    output_file = tmp_path / "output.json"
    input_file.write_text(json.dumps({"value": 21, "label": "Grüezi"}), encoding="utf-8")
    monkeypatch.setenv("TINY_APP_INPUT", str(input_file))
    monkeypatch.setenv("TINY_APP_OUTPUT", str(output_file))
    monkeypatch.chdir(tmp_path)
    source = (ROOT / "examples/package_acceptance/main.tiny").read_text(encoding="utf-8")
    runtime = Runtime(source)
    assert compile_and_run(source, runtime=runtime, module_path=tmp_path / "main.tiny") == "true\ntrue 42\n"
    assert json.loads(output_file.read_text(encoding="utf-8")) == {"value": 42, "label": "Grüezi"}
    assert runtime.heap_leak_report()["count"] == 0


def test_application_boundaries_join_workers_and_free_heap():
    """Denial paths and cancellation must leave no live heap allocations."""
    source = (ROOT / "examples/package_acceptance/boundaries.tiny").read_text(encoding="utf-8")
    runtime = Runtime(source)
    output = compile_and_run(source, runtime=runtime)
    assert "E_PERMISSION:network capability not enabled" in output
    assert "E_PERMISSION:process capability not enabled" in output
    assert "[PYSEC] module subprocess denied" in output
    assert "[PYDENY] attribute sqrt not allowed" in output
    assert output.endswith("true true true\n")
    assert runtime.heap_leak_report()["count"] == 0


def test_python_allowlist_is_not_a_filesystem_sandbox(tmp_path, monkeypatch):
    """An allowlisted Python function retains the host process's permissions."""
    outside = tmp_path / "outside.txt"
    outside.write_text("host data", encoding="utf-8")
    working = tmp_path / "working"
    working.mkdir()
    monkeypatch.chdir(working)
    module = ModuleType("acceptance_filesystem")
    module.read = lambda: outside.read_text(encoding="utf-8")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    output = compile_and_run('''
        def arguments = new[];
        def allow = new["read"];
        print(Python.call("acceptance_filesystem", "read", arguments, allow));
        def _cleanup_arguments = delete(arguments);
        def _cleanup_allow = delete(allow);
    ''')
    assert output == "host data\n"


def test_python_timeout_limits_waiting_and_does_not_abort_host_work(monkeypatch):
    """A timed-out Python thread can still finish; join it before test teardown."""
    release = threading.Event()
    finished = threading.Event()
    side_effects = []
    module = ModuleType("acceptance_timeout")

    def work():
        try:
            assert release.wait(5)
            side_effects.append("completed after timeout")
            return "late side effect"
        finally:
            finished.set()

    module.work = work
    monkeypatch.setitem(sys.modules, module.__name__, module)
    try:
        output = compile_and_run('''
            def arguments = new[];
            def allow = new["work"];
            try {
                def result = Python.call("acceptance_timeout", "work", arguments,
                    { allow: allow, timeout_ms: 1 });
                print(result);
            } catch (error) { print(error.message); }
            def _cleanup_arguments = delete(arguments);
            def _cleanup_allow = delete(allow);
        ''')
        assert "[PYTIMEOUT]" in output
        assert not finished.is_set()
        assert side_effects == []
    finally:
        release.set()
        assert finished.wait(5)
    assert side_effects == ["completed after timeout"]
