import io
import json
import os
import queue
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


def _debug_context(server: Any, messages: list[Dict[str, Any]], note: str | None = None) -> str:
    thread_alive = getattr(getattr(server, "_thread", None), "is_alive", lambda: False)()
    watchdog_alive = getattr(getattr(server, "_watchdog_thread", None), "is_alive", lambda: False)()
    queue_size = getattr(getattr(server, "_command_queue", None), "qsize", lambda: "unknown")()
    summary = {
        "note": note,
        "thread_alive": thread_alive,
        "watchdog_alive": watchdog_alive,
        "command_queue_size": queue_size,
        "events_seen": [m.get("event") for m in messages if m.get("type") == "event"],
        "last_messages": messages[-5:],
    }
    return json.dumps(summary, indent=2)


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
    assert not server._thread.is_alive(), _debug_context(server, messages, note="adapter run did not finish")

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
    assert not server._thread.is_alive(), _debug_context(server, messages, note="launch/configuration sequencing")


def test_output_events_stream_from_runtime(debug_server):
    _, server, messages, program = debug_server

    server.handle_initialize({"seq": 1, "command": "initialize"})
    server.handle_launch({"seq": 2, "command": "launch", "arguments": {"program": str(program)}})
    server.handle_configuration_done({"seq": 3, "command": "configurationDone"})

    server._thread.join(timeout=5)
    if server._thread.is_alive():
        server._command_queue.put("continue")
        server._thread.join(timeout=5)

    outputs = [msg for msg in messages if msg.get("event") == "output"]
    assert any(event.get("body", {}).get("output") == "5\n" for event in outputs)

    assert not server._thread.is_alive(), _debug_context(server, messages, note="runtime did not terminate")


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

    assert not server._thread.is_alive(), _debug_context(server, messages, note="configurationDone before launch flow")
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
    assert not server._thread.is_alive(), _debug_context(server, messages, note="namespace breakpoint thread alive")


def test_program_output_is_forwarded(debug_server):
    _, server, messages, program = debug_server

    program.write_text("print(42);", encoding="utf-8")
    server._command_queue.put("continue")

    server.handle_initialize({"seq": 1, "command": "initialize"})
    server.handle_launch({"seq": 2, "command": "launch", "arguments": {"program": str(program)}})
    server.handle_configuration_done({"seq": 3, "command": "configurationDone"})

    server._thread.join(timeout=5)
    assert not server._thread.is_alive(), _debug_context(server, messages, note="program output forwarding thread alive")

    output_events = [m for m in messages if m.get("type") == "event" and m.get("event") == "output"]
    assert any("42" in evt.get("body", {}).get("output", "") for evt in output_events)


def test_breakpoints_can_be_added_after_launch(tmp_path):
    module = load_adapter_module()
    server = module.DAPServer()
    messages = []
    server._send = messages.append  # type: ignore[assignment]
    program = tmp_path / "midrun.tiny"
    program.write_text(
        "\n".join(
            [
                "define x = 0;",
                "print(x);",
                "define x = 1;",
                "print(x);",
            ]
        ),
        encoding="utf-8",
    )

    # Start with an empty queue so the program pauses and waits for commands.
    server._command_queue = queue.Queue()

    server.handle_initialize({"seq": 1, "command": "initialize"})
    server.handle_set_breakpoints(
        {
            "seq": 2,
            "command": "setBreakpoints",
            "arguments": {"source": {"path": str(program)}, "breakpoints": [{"line": 2}]},
        }
    )
    server.handle_launch({"seq": 3, "command": "launch", "arguments": {"program": str(program)}})
    server.handle_configuration_done({"seq": 4, "command": "configurationDone"})

    # Wait for the first breakpoint to pause the program.
    for _ in range(50):
        if any(m.get("event") == "stopped" for m in messages):
            break
        time.sleep(0.1)
    else:
        raise AssertionError(f"Program did not pause: {messages!r}")

    # Add a new breakpoint while the program is paused and continue.
    server.handle_set_breakpoints(
        {
            "seq": 5,
            "command": "setBreakpoints",
            "arguments": {"source": {"path": str(program)}, "breakpoints": [{"line": 4}]},
        }
    )
    server.handle_continue({"seq": 6, "command": "continue"})

    # Wait for the newly added breakpoint to be hit.
    for _ in range(50):
        stopped_events = [m for m in messages if m.get("event") == "stopped"]
        if len(stopped_events) >= 2:
            break
        time.sleep(0.1)
    else:
        raise AssertionError(f"Second pause not observed: {messages!r}")

    server.handle_stack_trace({"seq": 7, "command": "stackTrace"})
    stack_resp = _response(messages, "stackTrace")
    assert stack_resp["body"]["stackFrames"][-1]["line"] == 4

    server.handle_continue({"seq": 8, "command": "continue"})
    server._thread.join(timeout=5)
    if server._thread.is_alive():
        server._command_queue.put("continue")
        server._thread.join(timeout=5)
    assert not server._thread.is_alive(), _debug_context(server, messages, note="post-breakpoint-continue thread alive")


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


def test_tcp_transport_does_not_disable_stdin(monkeypatch, tmp_path):
    module = load_adapter_module()

    # Use port 0 so the OS picks an ephemeral port without needing a real client.
    monkeypatch.setenv("TINYLANGUAGE_DAP_TCP_PORT", "0")
    monkeypatch.setenv("TINYLANGUAGE_DAP_TCP_HOST", "127.0.0.1")

    captured_env: dict[str, str | None] = {}

    def fake_compile_and_run(*_args, **_kwargs):
        captured_env["stdin_disabled"] = os.environ.get("TINYLANGUAGE_DAP_DISABLE_STDIN")
        return ""

    monkeypatch.setattr(module, "compile_and_run", fake_compile_and_run)

    program = tmp_path / "noop.tiny"
    program.write_text("print(1);", encoding="utf-8")

    server = module.DAPServer()
    server._writer = io.BytesIO()  # Prevent attempts to write to a real socket
    try:
        server._run_program(program)
    finally:
        server._close_transport()

    assert captured_env.get("stdin_disabled") != "1"
