from tiny_language import run_with_native_backend, run_with_python_bytecode_backend


def test_bytecode_backend_matches_native_simple_math() -> None:
    src = "define x = 2; define y = 3; print(x + y);"
    native_output = run_with_native_backend(src)
    bytecode_output = run_with_python_bytecode_backend(src)
    assert bytecode_output == native_output


def test_bytecode_backend_handles_functions_and_loops() -> None:
    src = """
    fn add_twice(a, b) {
        return a + b + b;
    }

    define total = 0;
    define i = 0;
    while (i < 3) {
        total = add_twice(total, i);
        i = i + 1;
    }
    print(total);
    """
    native_output = run_with_native_backend(src)
    bytecode_output = run_with_python_bytecode_backend(src)
    assert bytecode_output == native_output
