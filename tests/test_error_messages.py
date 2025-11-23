import pathlib
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from tiny_language import compile_and_run


def test_parser_error_includes_context():
    source = "define a = 1;\nprint(a;\n"

    with pytest.raises(Exception) as excinfo:
        compile_and_run(source)

    assert (
        str(excinfo.value)
        == "expected SYM ) (line 2, col 8)\n  1 | define a = 1;\n> 2 | print(a;\n    |        ^"
    )


def test_runtime_error_includes_context():
    source = "callme();\n"

    with pytest.raises(Exception) as excinfo:
        compile_and_run(source)

    assert (
        str(excinfo.value)
        == "call with return value must be bound; bare call statements are not allowed (offending call: callme()) (line 1, col 1)\n> 1 | callme();\n    | ^"
    )
