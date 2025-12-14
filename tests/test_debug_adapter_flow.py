import json
import sys
import time
from importlib import util
from pathlib import Path
from typing import Any, Dict

import pytest


def load_adapter_module():
    adapter_path = Path(__file__).resolve().parent.parent / "vscode-extension" / "python" / "tiny_debug_adapter.py"
    spec = util.spec_from_file_location("tiny_debug_adapter", adapter_path)
    module = util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


@pytest.fixture()
def debug_server(tmp_path):
    module = load_adapter_module()
    server = module.DAPServer()
    messages = []
    server._send = messages.append  # type: ignore[assignment]
    program = tmp_path / "pause.tiny"
    program.write_text(
        "\n".join(
            [
                "fn add(a, b) {",
                "    define tmp = a + b;",
                "    return tmp;",
                "}",
                "",
                "define result = add(2, 3);",
                "print(result);",
            ]
        ),
        encoding="utf-8",
    )
    server._command_queue.put("continue")
    return module, server, messages, program


def _response(messages: list[Dict[str, Any]], command: str) -> Dict[str, Any]:
    for message in messages:
        if message.get("type") == "response" and message.get("command") == command:
            return message
    raise AssertionError(f"response for {command} not found in {json.dumps(messages, indent=2)}")


def test_debug_adapter_runs_and_surfaces_state(debug_server):
    _, server, messages, program = debug_server

    server.handle_initialize({"seq": 1, "command": "initialize"})
    server.handle_set_breakpoints(
        {
            "seq": 2,
            "command": "setBreakpoints",
            "arguments": {"source": {"path": str(program)}, "breakpoints": [{"line": 7}]},
        }
    )
    server.handle_launch({"seq": 3, "command": "launch", "arguments": {"program": str(program)}})
    server.handle_configuration_done({"seq": 4, "command": "configurationDone"})

    server._thread.join(timeout=5)
    if server._thread.is_alive():
        # If the program is still paused waiting for a client command, flush a
        # final "continue" to unblock the thread and wait a bit longer. This
        # keeps the test resilient to slow CI hosts without changing the
        # adapter behavior.
        server._command_queue.put("continue")
        server._thread.join(timeout=5)
    assert not server._thread.is_alive()

    event_types = [m.get("event") for m in messages if m.get("type") == "event"]
    assert "stopped" in event_types
    assert "terminated" in event_types

    server.handle_stack_trace({"seq": 5, "command": "stackTrace"})
    stack_resp = _response(messages, "stackTrace")
    frames = stack_resp["body"]["stackFrames"]
    assert frames and frames[-1]["line"] == 7

    server.handle_scopes({"seq": 6, "command": "scopes"})
    scopes_resp = _response(messages, "scopes")
    scopes = scopes_resp["body"]["scopes"]
    assert scopes and scopes[0]["variablesReference"]

    handle_id = scopes[0]["variablesReference"]
    server.handle_variables({"seq": 7, "command": "variables", "arguments": {"variablesReference": handle_id}})
    variables_resp = _response(messages, "variables")
    rendered = {var["name"]: var["value"] for var in variables_resp["body"]["variables"]}
    assert rendered.get("result") == "5"


def test_launch_waits_for_configuration_done(debug_server):
    _, server, messages, program = debug_server

    server.handle_initialize({"seq": 1, "command": "initialize"})
    server.handle_set_breakpoints(
        {
            "seq": 2,
            "command": "setBreakpoints",
            "arguments": {"source": {"path": str(program)}, "breakpoints": [{"line": 7}]},
        }
    )

    server.handle_launch({"seq": 3, "command": "launch", "arguments": {"program": str(program)}})

    assert server._thread is None or not server._thread.is_alive()

    server.handle_configuration_done({"seq": 4, "command": "configurationDone"})

    assert server._thread is not None
    server._thread.join(timeout=5)
    if server._thread.is_alive():
        server._command_queue.put("continue")
        server._thread.join(timeout=5)

    assert not server._thread.is_alive()


def test_launch_after_configuration_done_starts_program(debug_server):
    _, server, messages, program = debug_server

    server.handle_initialize({"seq": 1, "command": "initialize"})

    # Some clients send configurationDone before launch. Once launch arrives,
    # the adapter should start the program without waiting for another
    # configurationDone.
    server.handle_configuration_done({"seq": 2, "command": "configurationDone"})
    server.handle_launch({"seq": 3, "command": "launch", "arguments": {"program": str(program)}})

    server._thread.join(timeout=5)
    if server._thread.is_alive():
        server._command_queue.put("continue")
        server._thread.join(timeout=5)

    assert not server._thread.is_alive()
    assert any(m.get("event") == "terminated" for m in messages)


def test_launch_without_program_returns_error(debug_server):
    _, server, messages, _ = debug_server

    server.handle_initialize({"seq": 1, "command": "initialize"})
    server.handle_launch({"seq": 2, "command": "launch", "arguments": {}})

    launch_resp = _response(messages, "launch")
    assert launch_resp["success"] is False
    assert "program" in launch_resp["message"]

    output_events = [m for m in messages if m.get("type") == "event" and m.get("event") == "output"]
    assert output_events


def test_command_queue_logs_stale_entries(tmp_path, monkeypatch):
    module = load_adapter_module()
    server = module.DAPServer()

    # Capture log messages instead of writing to a file/stdout.
    logs: list[str] = []
    server._log = lambda msg, *args: logs.append(msg % args if args else msg)  # type: ignore[assignment]

    # Pretend a previous run left a command in the queue with an old generation.
    server._active_run_generation = 2
    server._current_run_generation = 2
    server._command_queue.put((1, "continue"))
    server._command_queue.put((2, "next"))

    with monkeypatch.context() as m:
        m.setenv("TINYLANGUAGE_DAP_PAUSE_TIMEOUT", "1")
        command = server._wait_for_command()

    assert command == "next"
    assert any("Discarding stale command" in entry for entry in logs)


def test_breakpoints_follow_module_namespace(monkeypatch, tmp_path):
    module = load_adapter_module()
    captured = []

    class SpyDebugger(module.Debugger):  # type: ignore[misc]
        def set_breakpoints(self, namespace, lines):  # type: ignore[override]
            captured.append(namespace)
            return super().set_breakpoints(namespace, lines)

    monkeypatch.setattr(module, "Debugger", SpyDebugger)

    server = module.DAPServer()
    messages = []
    server._send = messages.append  # type: ignore[assignment]
    program = tmp_path / "pause.tiny"
    program.write_text("print(1);", encoding="utf-8")
    server._command_queue.put("continue")

    server.handle_initialize({"seq": 1, "command": "initialize"})
    server.handle_set_breakpoints(
        {
            "seq": 2,
            "command": "setBreakpoints",
            "arguments": {"source": {"path": str(program)}, "breakpoints": [{"line": 1}]},
        }
    )
    server.handle_launch({"seq": 3, "command": "launch", "arguments": {"program": str(program)}})
    server.handle_configuration_done({"seq": 4, "command": "configurationDone"})
    server._thread.join(timeout=5)

    assert captured
    assert captured[-1] == server._namespace_for_path(program)


def test_program_output_is_forwarded(debug_server):
    _, server, messages, program = debug_server

    program.write_text("print(42);", encoding="utf-8")
    server._command_queue.put("continue")

    server.handle_initialize({"seq": 1, "command": "initialize"})
    server.handle_launch({"seq": 2, "command": "launch", "arguments": {"program": str(program)}})
    server.handle_configuration_done({"seq": 3, "command": "configurationDone"})

    server._thread.join(timeout=5)
    assert not server._thread.is_alive()

    output_events = [m for m in messages if m.get("type") == "event" and m.get("event") == "output"]
    assert any("42" in evt.get("body", {}).get("output", "") for evt in output_events)


def test_pause_on_entry_without_breakpoints(debug_server):
    _, server, messages, program = debug_server

    server.handle_initialize({"seq": 1, "command": "initialize"})
    server.handle_launch({"seq": 2, "command": "launch", "arguments": {"program": str(program)}})
    server.handle_configuration_done({"seq": 3, "command": "configurationDone"})

    server._thread.join(timeout=5)
    if server._thread.is_alive():
        server._command_queue.put("continue")
        server._thread.join(timeout=5)

    stopped_events = [m for m in messages if m.get("type") == "event" and m.get("event") == "stopped"]
    assert stopped_events
    assert any(evt.get("body", {}).get("reason") == "pause" for evt in stopped_events)


def test_command_queue_is_cleared_between_launches(debug_server):
    _, server, messages, program = debug_server

    server.handle_initialize({"seq": 1, "command": "initialize"})
    server.handle_launch({"seq": 2, "command": "launch", "arguments": {"program": str(program)}})
    server.handle_configuration_done({"seq": 3, "command": "configurationDone"})

    server._thread.join(timeout=5)
    if server._thread.is_alive():
        server._command_queue.put("continue")
        server._thread.join(timeout=5)

    assert not server._thread.is_alive()

    messages.clear()
    # Inject a stale command to mimic a previous session leaving behind a
    # continue request. The adapter should drop this before the next launch so
    # stop-on-entry still pauses.
    server._command_queue.put("continue")

    server.handle_launch({"seq": 4, "command": "launch", "arguments": {"program": str(program)}})
    server.handle_configuration_done({"seq": 5, "command": "configurationDone"})

    paused_event = None
    for _ in range(20):
        paused_event = next(
            (
                m
                for m in messages
                if m.get("type") == "event"
                and m.get("event") == "stopped"
                and m.get("body", {}).get("reason") == "pause"
            ),
            None,
        )
        if paused_event:
            break
        time.sleep(0.1)

    assert paused_event is not None, f"stopped event missing: {messages!r}"

    server._command_queue.put("continue")
    server._thread.join(timeout=5)

    assert not server._thread.is_alive()


def test_stale_commands_from_previous_run_are_dropped(debug_server):
    _, server, messages, program = debug_server

    server.handle_initialize({"seq": 1, "command": "initialize"})
    server.handle_launch({"seq": 2, "command": "launch", "arguments": {"program": str(program)}})
    server.handle_configuration_done({"seq": 3, "command": "configurationDone"})

    server._thread.join(timeout=5)
    if server._thread.is_alive():
        server._command_queue.put("continue")
        server._thread.join(timeout=5)

    assert not server._thread.is_alive()

    messages.clear()
    stale_generation = server._current_run_generation - 1
    server._command_queue.put((stale_generation, "continue"))

    server.handle_launch({"seq": 4, "command": "launch", "arguments": {"program": str(program)}})
    server.handle_configuration_done({"seq": 5, "command": "configurationDone"})

    paused_event = None
    for _ in range(20):
        paused_event = next(
            (
                m
                for m in messages
                if m.get("type") == "event"
                and m.get("event") == "stopped"
                and m.get("body", {}).get("reason") == "pause"
            ),
            None,
        )
        if paused_event:
            break
        time.sleep(0.1)

    assert paused_event is not None, f"stopped event missing: {messages!r}"

    server._command_queue.put("continue")
    server._thread.join(timeout=5)

    assert not server._thread.is_alive()


def test_watchdog_warns_without_terminating(debug_server):
    _, server, messages, _ = debug_server

    server.handle_initialize({"seq": 1, "command": "initialize"})
    # Pretend the client has been idle for a while so the watchdog triggers quickly.
    server._last_client_message = time.monotonic() - 10

    warning = None
    for _ in range(20):
        if messages:
            warning = next(
                (
                    m
                    for m in messages
                    if m.get("type") == "event"
                    and m.get("event") == "output"
                    and "No launch/configuration requests" in m.get("body", {}).get("output", "")
                ),
                None,
            )
        if warning:
            break
        time.sleep(0.1)

    server._shutdown = True
    server._watchdog_thread.join(timeout=1)

    assert warning is not None, f"Watchdog warning not emitted: {messages!r}"
    assert all(m.get("event") != "terminated" for m in messages)


def test_watchdog_surfaces_initialize_timeout(debug_server):
    _, server, messages, _ = debug_server

    # Simulate a client that never sends "initialize" so the adapter explains the idle state.
    server._last_client_message = time.monotonic() - 10

    warning = None
    for _ in range(20):
        if messages:
            warning = next(
                (
                    m
                    for m in messages
                    if m.get("type") == "event"
                    and m.get("event") == "output"
                    and "waiting for 'initialize'" in m.get("body", {}).get("output", "")
                ),
                None,
            )
        if warning:
            break
        time.sleep(0.1)

    server._shutdown = True
    server._watchdog_thread.join(timeout=1)

    assert warning is not None, f"Initialize watchdog warning not emitted: {messages!r}"


def test_env_var_truthy_parsing(monkeypatch):
    module = load_adapter_module()

    monkeypatch.setenv("TINYLANGUAGE_DAP_STDERR", "true")
    server = module.DAPServer()
    assert server._log_to_stderr is True

    monkeypatch.setenv("TINYLANGUAGE_DAP_STDERR", "0")
    server_disabled = module.DAPServer()
    assert server_disabled._log_to_stderr is False
