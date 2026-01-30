"""Tests for the stdlib http module stub."""

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
