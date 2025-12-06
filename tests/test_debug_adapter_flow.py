import json
import sys
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
    return server, messages, program


def _response(messages: list[Dict[str, Any]], command: str) -> Dict[str, Any]:
    for message in messages:
        if message.get("type") == "response" and message.get("command") == command:
            return message
    raise AssertionError(f"response for {command} not found in {json.dumps(messages, indent=2)}")


def test_debug_adapter_runs_and_surfaces_state(debug_server):
    server, messages, program = debug_server

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


def test_launch_without_program_returns_error(debug_server):
    server, messages, _ = debug_server

    server.handle_initialize({"seq": 1, "command": "initialize"})
    server.handle_launch({"seq": 2, "command": "launch", "arguments": {}})

    launch_resp = _response(messages, "launch")
    assert launch_resp["success"] is False
    assert "program" in launch_resp["message"]

    output_events = [m for m in messages if m.get("type") == "event" and m.get("event") == "output"]
    assert output_events
