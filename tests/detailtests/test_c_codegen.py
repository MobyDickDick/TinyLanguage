from tiny_language import compile_to_c_source


def test_c_codegen_supports_non_numeric_variables() -> None:
    source = 'define greeting = "hi"; define ok = true; print(greeting, ok);'

    c_source = compile_to_c_source(source)

    assert 'VAL_STRING_VALUE("hi")' in c_source
    assert "VAL_BOOL_VALUE(true)" in c_source
    assert 'ARG_STRING_VALUE("greeting")' in c_source
    assert 'ARG_STRING_VALUE("ok")' in c_source
