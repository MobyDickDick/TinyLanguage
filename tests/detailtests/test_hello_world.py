import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT / "src"))

from tiny_language import compile_and_run


def test_hello_world_output_matches_readme_example():
    hello_world_path = PROJECT_ROOT / "src_tiny" / "hello_world.tiny"

    output = compile_and_run(hello_world_path.read_text())

    assert output == "Hello, TinyLanguage!\n"
