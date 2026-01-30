"""Lightweight smoke tests for quick developer feedback."""

from tests.utils import execute_tiny_program, run_tiny


def test_smoke_run_tiny_addition() -> None:
    """Ensure in-process execution works for a simple program."""
    source = "\n".join(
        [
            "fn add(a, b) { return a + b; }",
            "print(add(2, 3));",
        ]
    )
    assert run_tiny(source).strip() == "5"


def test_smoke_cli_execution() -> None:
    """Ensure CLI execution handles a tiny program cleanly."""
    result = execute_tiny_program('print("hello");\n')
    assert result.returncode == 0
    assert result.stdout.strip() == "hello"
    assert result.stderr.strip() == ""


def test_smoke_stdlib_module_usage() -> None:
    """Ensure new stdlib modules load and execute simple paths."""
    source = "\n".join(
        [
            "import stdlib.argparse;",
            "import stdlib.csv;",
            "import stdlib.logging;",
            "import stdlib.os;",
            "import stdlib.path;",
            "import stdlib.regex;",
            "import stdlib.string;",
            "import stdlib.time;",
            "",
            "def parts = new[\"/tmp\", \"tiny\"];",
            "print(path.join(parts));",
            "def _cleanup_parts = delete(parts);",
            "",
            "print(os.path_separator());",
            "",
            "def rows = csv.parse(\"a,b\\nc,d\");",
            "print(Collections.len(rows));",
            "def _cleanup_rows = delete(rows);",
            "",
            "print(regex.replace(\"tiny\", \"tiny language\", \"large\"));",
            "",
            "def args = new[\"--count=3\", \"file.txt\"];",
            "def flag = Map.new();",
            "def _flag_name = Map.set(flag, \"name\", \"count\");",
            "def _flag_long = Map.set(flag, \"long\", \"count\");",
            "def _flag_type = Map.set(flag, \"type\", \"number\");",
            "def flags = new[flag];",
            "def _cleanup_flag = delete(flag);",
            "def positional = Map.new();",
            "def _pos_name = Map.set(positional, \"name\", \"path\");",
            "def positionals = new[positional];",
            "def _cleanup_positional = delete(positional);",
            "def spec = { flags: flags, positionals: positionals };",
            "def parsed = argparse.parse(args, spec);",
            "print(Map.get(parsed, \"count\", 0));",
            "print(Map.get(parsed, \"path\", \"\"));",
            "def _cleanup_args = delete(args);",
            "def _cleanup_flags = delete(flags);",
            "def _cleanup_positionals = delete(positionals);",
            "def _cleanup_parsed = delete(parsed);",
            "",
            "def log_line = logging.format(\"info\", \"hello\", Null, \"2024-01-01T00:00:00Z\");",
            "print(string.contains(log_line, \"\\\"level\\\":\\\"info\\\"\"));",
            "",
            "print(time.now_ms() >= 0);",
        ]
    )
    lines = run_tiny(source).strip().splitlines()
    assert lines[0] == "/tmp/tiny"
    assert lines[1] in {"/", "\\"}
    assert int(lines[2]) == 2
    assert lines[3] == "large language"
    assert float(lines[4]) == 3.0
    assert lines[5] == "file.txt"
    assert lines[6] == "true"
    assert lines[7] == "true"
