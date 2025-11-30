import pathlib
import re
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from tiny_language import compile_and_run


def test_heap_pointer_demo_outputs_errors_and_hints():
    program = PROJECT_ROOT / "src_tiny" / "heap_pointer_demo.tiny"

    output = compile_and_run(program.read_text())

    assert output.startswith("=== Sichere Heap-Nutzung ===\nLesewert fuer Index:\n2\n30\n")
    assert "bewusst provoziert; das Programm laeuft trotzdem weiter" in output
    assert "Aufgezeichnete Out-of-Bounds-Meldung:" in output
    assert "Aufgezeichnete Missing-Field-Meldung:" in output

    assert len(re.findall(r"\[E000\] heap access error: index 5 out of range", output)) == 1
    assert len(re.findall(r"\[E000\] unknown field missing", output)) == 1

    assert re.search(r"> 39 \| define ignored_oob = heap_get\(too_short, 5\); // Runtime-Fehler wird aufgezeichnet", output)
    assert re.search(r"> 51 \| define ignored_missing = record\.missing; // Meldet \"unknown field missing\"", output)
