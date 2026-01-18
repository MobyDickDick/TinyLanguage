import pytest

from tiny_language import _parse_and_lint


def _lint_with_heap_checks(source: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TINY_LINT_HEAP", "1")
    _parse_and_lint(source)


def test_heap_bounds_check(monkeypatch: pytest.MonkeyPatch) -> None:
    source = "def ptr = new[1, 2];\nprint(heap_get(ptr, 2));"
    with pytest.raises(Exception) as excinfo:
        _lint_with_heap_checks(source, monkeypatch)
    assert "out of bounds" in str(excinfo.value)


def test_heap_aliasing_check(monkeypatch: pytest.MonkeyPatch) -> None:
    source = "def ptr = new(2);\ndef alias = ptr;\nprint(alias);"
    with pytest.raises(Exception) as excinfo:
        _lint_with_heap_checks(source, monkeypatch)
    assert "ownership" in str(excinfo.value)
