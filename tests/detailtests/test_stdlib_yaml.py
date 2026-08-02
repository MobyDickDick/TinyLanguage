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

    assert "a: 1" in out
    assert "b: [true,null]" in out


def test_stdlib_yaml_round_trip_preserves_json_compatible_scalars(run_tiny_source):
    """Reparse rendered YAML without changing supported scalar types or values."""
    out = run_tiny_source(
        '''
        import stdlib.yaml;
        def original = yaml.parse("integer: 42\nnegative: -7\ndecimal: 3.5\nflag: true\nempty: \\\"\\\"\nlabel: Grüße\nitems: [1,\\\"two\\\",false,null]\n");
        def rendered = yaml.stringify(original);
        def reparsed = yaml.parse(rendered);
        print(JSON.stringify(reparsed));
        def _cleanup_original = delete(original);
        def _cleanup_reparsed = delete(reparsed);
        ''',
    )

    expected = '{"integer":42,"negative":-7,"decimal":3.5,"flag":true,"empty":"","label":"Gr\\u00fc\\u00dfe","items":[1,"two",false,null]}'
    assert out == f"{expected}\n"


def test_stdlib_yaml_parses_nested_block_maps_and_lists(run_tiny_source):
    """Parse nested indentation-based collections in the conservative subset."""
    out = run_tiny_source(
        '''
        import stdlib.yaml;
        def value = yaml.parse("project:\n  name: Tiny\n  releases:\n    - 1\n    - 2\n  metadata:\n    stable: true\n    note: null\n");
        print(JSON.stringify(value));
        def _cleanup_value = delete(value);
        ''',
    )

    expected = '{"project":{"name":"Tiny","releases":[1,2],"metadata":{"stable":true,"note":null}}}'
    assert out == f"{expected}\n"


def test_stdlib_yaml_parses_inline_maps_in_block_lists(run_tiny_source):
    """Parse list items whose first mapping key shares the item marker line."""
    out = run_tiny_source(
        '''
        import stdlib.yaml;
        def value = yaml.parse("projects:\n  - name: Tiny\n    stable: true\n    releases:\n      - 1\n      - 2\n  - name: Tools\n    homepage: https://example.test/tools\n");
        print(JSON.stringify(value));
        def _cleanup_value = delete(value);
        ''',
    )

    expected = '{"projects":[{"name":"Tiny","stable":true,"releases":[1,2]},{"name":"Tools","homepage":"https://example.test/tools"}]}'
    assert out == f"{expected}\n"


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
