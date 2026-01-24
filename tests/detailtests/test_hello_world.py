"""Checks that the hello world TinyLanguage sample matches README output."""

import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
# Allow importing TinyLanguage from the src directory during tests.
sys.path.append(str(PROJECT_ROOT / "src"))

from tiny_language import compile_and_run


def test_hello_world_output_matches_readme_example():
    """Compile and run the sample, ensuring output stays stable."""
    hello_world_path = PROJECT_ROOT / "src_tiny" / "hello_world.tiny"

    # Execute the example program.
    output = compile_and_run(hello_world_path.read_text())

    # Output should match the README's hello world snippet.
    assert output == "Hello, TinyLanguage!\n"
