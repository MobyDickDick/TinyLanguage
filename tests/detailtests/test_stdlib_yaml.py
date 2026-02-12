"""Coverage tests for the stdlib yaml module."""


def test_stdlib_yaml_round_trip_mapping_and_sequence(run_tiny_source):
    """Parse a compact YAML mapping and render it back to text."""
    out = run_tiny_source(
        """
        import stdlib.yaml;
        def value = yaml.parse("a: 1\nb: [true, null]\n");
        def text = yaml.stringify(value);
        print(text);
        def _cleanup_value = delete(value);
        """,
    )

    assert "a: \"1\"" in out
    assert "b: [true,null]" in out


def test_stdlib_yaml_load_dump_round_trip(run_tiny_source, tmp_path):
    """Load a YAML file and dump it again via stdlib helpers."""
    yaml_path = tmp_path / "sample.yaml"
    yaml_path.write_text("flag: true\nname: tiny\n", encoding="utf-8")

    out = run_tiny_source(
        f"""
        import stdlib.yaml;
        def value = yaml.load("{yaml_path}");
        def _dumped = yaml.dump("{yaml_path}", value);
        def _cleanup_value = delete(value);
        print(File.read("{yaml_path}"));
        """,
    )

    assert "flag: true" in out
    assert "name: \"tiny\"" in out
