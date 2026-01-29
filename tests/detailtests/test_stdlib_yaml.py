"""Placeholder tests for the stdlib yaml module stub."""

import pytest


@pytest.mark.xfail(reason="stdlib.yaml stub not implemented yet", strict=False)
def test_stdlib_yaml_round_trip_placeholder(run_tiny_source):
    """Document the expected parse/stringify round trip for YAML."""
    out = run_tiny_source(
        """
        import stdlib.yaml;
        def value = yaml.parse("a: 1\nb: [true, null]\n");
        def text = yaml.stringify(value);
        print(text);
        def _cleanup_value = delete(value);
        """,
    )

    assert "a:" in out
    assert "b:" in out


@pytest.mark.xfail(reason="stdlib.yaml stub not implemented yet", strict=False)
def test_stdlib_yaml_load_dump_placeholder(run_tiny_source, tmp_path):
    """Document the expected file-based helpers for YAML."""
    yaml_path = tmp_path / "sample.yaml"
    yaml_path.write_text("flag: true\n")

    out = run_tiny_source(
        f"""
        import stdlib.yaml;
        def value = yaml.load(\"{yaml_path}\");
        def _dumped = yaml.dump(\"{yaml_path}\", value);
        def _cleanup_value = delete(value);
        print(File.read(\"{yaml_path}\"));
        """,
    )

    assert "flag" in out
