import pytest

from tiny_language import TinyLangError, compile_and_run


def test_unused_binding_prefixed_with_underscore_is_ignored():
    assert compile_and_run("define _unused = 1;") == ""


def test_bare_call_to_returning_function_fails():
    src = """
    fn greet() -> string { return "hi"; }
    greet();
    """
    with pytest.raises(TinyLangError):
        compile_and_run(src)


def test_imports_must_precede_code():
    src = """
    define a = 1;
    import tools;
    """
    with pytest.raises(TinyLangError):
        compile_and_run(src)
