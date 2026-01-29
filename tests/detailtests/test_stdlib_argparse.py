"""Tests for the stdlib argparse module."""

import pytest


def test_stdlib_argparse_parses_flags_and_positionals(run_tiny_source):
    """Parse flags and positional arguments with defaults."""
    out = run_tiny_source(
        """
        import stdlib.argparse;

        def args = new["--count", "3", "-v", "input.txt"];
        def flags = new[
          { name: "verbose", short: "v", long: "verbose", takes_value: false, default_value: false },
          { name: "count", short: "c", long: "count", takes_value: true, default_value: "1" }
        ];
        def positionals = new[
          { name: "input", required: true },
          { name: "output", default_value: "out.txt" }
        ];
        def spec = { flags: flags, positionals: positionals };
        def parsed = argparse.parse(args, spec);
        print(Map.get(parsed, "verbose"));
        print(Map.get(parsed, "count"));
        print(Map.get(parsed, "input"));
        print(Map.get(parsed, "output"));
        def _cleanup_parsed = delete(parsed);
        def _cleanup_args = delete(args);
        def _cleanup_flags = delete(flags);
        def _cleanup_positionals = delete(positionals);
        """,
    )

    assert out == "true\n3\ninput.txt\nout.txt\n"


def test_stdlib_argparse_unknown_flag(run_tiny_source):
    """Unknown flags should raise a ValueError."""
    with pytest.raises(Exception, match=r"unknown flag --oops"):
        run_tiny_source(
            """
            import stdlib.argparse;

            def args = new["--oops"];
            def spec = { flags: new[], positionals: new[] };
            def _parsed = argparse.parse(args, spec);
            def _cleanup_args = delete(args);
            """,
        )


def test_stdlib_argparse_missing_value(run_tiny_source):
    """Flags that require a value should error when one is missing."""
    with pytest.raises(Exception, match=r"flag --count expects a value"):
        run_tiny_source(
            """
            import stdlib.argparse;

            def args = new["--count"];
            def flags = new[
              { name: "count", long: "count", takes_value: true }
            ];
            def spec = { flags: flags, positionals: new[] };
            def _parsed = argparse.parse(args, spec);
            def _cleanup_args = delete(args);
            def _cleanup_flags = delete(flags);
            """,
        )


def test_stdlib_argparse_missing_required_positional(run_tiny_source):
    """Required positional arguments should be validated."""
    with pytest.raises(Exception, match=r"missing required argument input"):
        run_tiny_source(
            """
            import stdlib.argparse;

            def args = new[];
            def positionals = new[
              { name: "input", required: true }
            ];
            def spec = { flags: new[], positionals: positionals };
            def _parsed = argparse.parse(args, spec);
            def _cleanup_args = delete(args);
            def _cleanup_positionals = delete(positionals);
            """,
        )
