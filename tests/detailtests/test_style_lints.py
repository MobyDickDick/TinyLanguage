import pytest

from tiny_language import TinyLangError, compile_and_run


def test_unused_binding_prefixed_with_underscore_is_ignored():
    assert compile_and_run("def _unused = 1;") == ""


def test_bare_call_to_returning_function_fails():
    src = """
    fn greet() -> string { return "hi"; }
    def _unused1 = greet();
    """
    with pytest.raises(TinyLangError):
        compile_and_run(src)


def test_imports_must_precede_code():
    src = """
    def a = 1;
    import tools;
    """
    with pytest.raises(TinyLangError):
        compile_and_run(src)


def test_unreachable_after_return_is_flagged():
    src = """
    fn unreachable() {
        return 1;
        def x = 2;
    }
    """
    with pytest.raises(TinyLangError) as err:
        compile_and_run(src)
    assert "unreachable" in str(err.value).lower()


def test_unreachable_after_exhaustive_if_is_flagged():
    src = """
    fn chooser(flag) {
        if (flag) { return 1; } else { return 2; }
        print(flag);
    }
    """
    with pytest.raises(TinyLangError) as err:
        compile_and_run(src)
    assert "unreachable" in str(err.value).lower()


def test_type_change_is_flagged_even_without_execution():
    src = """
    fn skipped() {
        def i = 1;
        i = "oops";
    }
    """

    with pytest.raises(TinyLangError) as err:
        compile_and_run(src)

    assert "type change" in str(err.value)
