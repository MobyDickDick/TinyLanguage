from tiny_language import ModuleResolver, Runtime, compile_and_run


def test_import_caching_and_binding(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    module_file = pkg / "counter.tiny"
    module_file.write_text(
        """
        define load_count = 1;
        print("loaded " + String.repeat("!", load_count));
        """,
        encoding="utf-8",
    )

    runtime = Runtime("")
    resolver = ModuleResolver(search_paths=[tmp_path])
    program = """
    import pkg.counter;
    print(counter.load_count);
    import pkg.counter as alias;
    print(alias.load_count);
    """

    output = compile_and_run(
        program,
        runtime=runtime,
        module_resolver=resolver,
        module_path=tmp_path / "main.tiny",
        module_namespace="main",
    )

    assert output.splitlines() == ["loaded !", "1", "1"]


def test_relative_import_uses_caller_namespace(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    util_file = pkg / "util.tiny"
    util_file.write_text(
        """
        define label = "from util";
        print(label);
        """,
        encoding="utf-8",
    )

    core_file = pkg / "core.tiny"
    core_file.write_text(
        """
        import .util;
        print(util.label);
        """,
        encoding="utf-8",
    )

    runtime = Runtime("")
    resolver = ModuleResolver(search_paths=[tmp_path])
    output = compile_and_run(
        core_file.read_text(encoding="utf-8"),
        runtime=runtime,
        module_resolver=resolver,
        module_path=core_file,
        module_namespace="pkg.core",
    )

    assert output.splitlines() == ["from util", "from util"]
