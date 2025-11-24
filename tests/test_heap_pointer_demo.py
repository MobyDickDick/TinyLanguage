import pathlib
import re
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from tiny_language import compile_and_run


def test_heap_pointer_demo_outputs_errors_and_hints():
    program = PROJECT_ROOT / "heap_pointer_demo.tiny"

    output = compile_and_run(program.read_text())

    assert output.startswith("30\nNone\n")
    assert output.count("heap access error: index 5 out of range") >= 2
    assert "unknown field missing" in output

    assert re.search(r"> 26 \| print\(heap_get\(too_short, 5\)\); // Wirft einen Laufzeitfehler", output)
    assert re.search(r"> 33 \| print\(record\.missing\);", output)
