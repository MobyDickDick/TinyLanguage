"""Tests for stdlib sources."""

from __future__ import annotations

from pathlib import Path

import pytest

from tiny_language import Lexer, Parser

PROJECT_ROOT = Path(__file__).resolve().parents[2]

STDLIB_MODULES = [
    PROJECT_ROOT / "stdlib" / "argparse.tiny",
    PROJECT_ROOT / "stdlib" / "collections.tiny",
    PROJECT_ROOT / "stdlib" / "csv.tiny",
    PROJECT_ROOT / "stdlib" / "datetime.tiny",
    PROJECT_ROOT / "stdlib" / "fswatch.tiny",
    PROJECT_ROOT / "stdlib" / "http.tiny",
    PROJECT_ROOT / "stdlib" / "io.tiny",
    PROJECT_ROOT / "stdlib" / "logging.tiny",
    PROJECT_ROOT / "stdlib" / "math.tiny",
    PROJECT_ROOT / "stdlib" / "json.tiny",
    PROJECT_ROOT / "stdlib" / "os.tiny",
    PROJECT_ROOT / "stdlib" / "path.tiny",
    PROJECT_ROOT / "stdlib" / "pathlib.tiny",
    PROJECT_ROOT / "stdlib" / "process.tiny",
    PROJECT_ROOT / "stdlib" / "random.tiny",
    PROJECT_ROOT / "stdlib" / "regex.tiny",
    PROJECT_ROOT / "stdlib" / "statistics.tiny",
    PROJECT_ROOT / "stdlib" / "string.tiny",
    PROJECT_ROOT / "stdlib" / "toml.tiny",
    PROJECT_ROOT / "stdlib" / "time.tiny",
    PROJECT_ROOT / "stdlib" / "yaml.tiny",
]


def _parse_demo(path: Path) -> None:
    """Helper to parse demo."""
    source = path.read_text(encoding="utf-8")
    Parser(Lexer(source), source).parse()


@pytest.mark.parametrize("demo_path", STDLIB_MODULES)
def test_stdlib_sources_parse(demo_path: Path) -> None:
    """Test that stdlib sources parse."""
    assert demo_path.exists()
    _parse_demo(demo_path)
