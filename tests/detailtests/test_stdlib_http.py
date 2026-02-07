"""Tests for the stdlib http module stub."""

import json
import random

from tests.detailtests.stdlib_helpers import run_stdlib_module


def test_stdlib_http_mock_timeout(run_tiny_source):
    """Ensure mocked timeout paths return a deterministic timeout error."""
    out = run_stdlib_module(
        run_tiny_source,
        "http",
        """
        def res = http.get("mock://timeout", Null);
        def rendered = match(res) {
          case Ok { value: resp } => "ok";
          case Err { code: code, message: message } => code + "\\n" + message;
        };
        print(rendered);
        """,
    )

    assert out == "E_TIMEOUT\nrequest timed out\n"


def test_stdlib_http_invalid_url(run_tiny_source):
    """Ensure invalid inputs surface as E_INVALID errors."""
    out = run_stdlib_module(
        run_tiny_source,
        "http",
        """
        def res = http.get("", Null);
        def rendered = match(res) {
          case Ok { value: resp } => "ok";
          case Err { code: code, message: message } => code + "\\n" + message;
        };
        print(rendered);
        """,
    )

    assert out == "E_INVALID\nurl required\n"


def test_stdlib_http_echo_roundtrip_fuzzed(run_tiny_source):
    """Ensure mock echo endpoint round-trips request bodies."""
    rng = random.Random(2)
    payloads = [
        "".join(rng.choice("abcXYZ123 ") for _ in range(rng.randint(0, 12)))
        for _ in range(12)
    ]
    program_lines = []
    for idx, payload in enumerate(payloads):
        literal = json.dumps(payload)
        program_lines.append(
            f"""
            def res_{idx} = http.post("mock://echo", "ignored", {{ body: {literal} }});
            def rendered_{idx} = match(res_{idx}) {{
              case Ok {{ value: resp }} => Map.get(resp, "body", "");
              case Err {{ code: code, message: message }} => code + ":" + message;
            }};
            print(rendered_{idx});
            def _cleanup_res_{idx} = delete(res_{idx});
            """
        )
    out = run_stdlib_module(run_tiny_source, "http", "\n".join(program_lines))
    lines = [line for line in out.splitlines()]
    assert lines == payloads
