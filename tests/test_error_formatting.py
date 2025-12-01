import textwrap

from tiny_language import SourcePos, SourceSpan, TinyLangError, _format_error_for_source


def test_format_error_includes_code_hint_and_span():
    source = textwrap.dedent(
        """
        define value = 1 + 2;
        print(value);
        """
    ).strip()
    start = SourcePos(1, 8)
    stop = SourcePos(1, 12)
    err = TinyLangError("example failure", start, code="E123", hint="Check the expression", span=SourceSpan(start, stop))

    formatted = _format_error_for_source(source, err)

    assert "[E123] example failure" in formatted
    assert "Hint: Check the expression" in formatted
    assert "^^^^^" in formatted
