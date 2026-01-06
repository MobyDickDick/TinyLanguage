from tiny_language import compile_and_run, compile_to_python_source, run_with_python_backend


def test_python_backend_executes_basic_program():
    src = """
    fn add(x, y) {
        return x + y;
    }

    def total = add(2, 3);
    print(total);
    """

    interpreted = compile_and_run(src)
    generated = run_with_python_backend(src)

    assert interpreted == "5\n"
    assert generated == interpreted


def test_emit_python_source_contains_entrypoint():
    src = "print(1 + 1);"
    emitted = compile_to_python_source(src)

    assert "def tiny_main" in emitted
