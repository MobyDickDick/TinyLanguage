"""Tests for the Tiny program repository SQLite adapter."""

from __future__ import annotations

import subprocess
import sys

from tiny_program_repository_db_adapter import TinyProgramRepositoryDB


def test_schema_and_step_execution_and_unreachable_detection(tmp_path):
    """Adapter can initialize schema, step program, and report unreachable PCs."""
    db = TinyProgramRepositoryDB(tmp_path / "tiny_repo.db")
    db.initialize_schema()

    program_id = db.register_program("demo", "demo source")
    db.add_statement(program_id, 0, "set", "set x = x", {"var_name": "x", "value_expr": "x"})
    db.add_statement(program_id, 1, "goto", "goto done", {"target_label": "done"})
    db.add_statement(program_id, 2, "print", "print never", {"value_expr": "never"})
    db.add_statement(program_id, 3, "label", "done:", {"label_name": "done"})
    db.add_statement(program_id, 4, "print", "print ok", {"value_expr": "ok"})

    env = {"x": True, "ok": "OK", "never": "NOPE"}
    step0 = db.step(program_id, 0, env)
    assert step0.next_pc == 1

    step1 = db.step(program_id, step0.next_pc, env)
    assert step1.next_pc == 3

    step2 = db.step(program_id, step1.next_pc, env)
    assert step2.next_pc == 4

    step3 = db.step(program_id, step2.next_pc, env)
    assert step3.output == "OK"

    assert db.find_unreachable_pcs(program_id) == [2]
    db.close()


def test_source_to_db_and_db_to_source_roundtrip(tmp_path):
    db = TinyProgramRepositoryDB(tmp_path / "roundtrip.db")
    db.initialize_schema()

    source = """
# comment
start:
set x = 1
if x goto done
print never

goto start

done:
print x
"""
    program_id = db.source_to_db("roundtrip", source)

    reconstructed = db.db_to_source(program_id)
    assert reconstructed == "\n".join(
        [
            "start:",
            "set x = 1",
            "if x goto done",
            "print never",
            "goto start",
            "done:",
            "print x",
        ]
    )
    db.close()


def test_source_equivalence_normalizes_whitespace_and_comments():
    source_a = """
start:
set x=1
if x goto end
print never
end:
print x
"""
    source_b = """
# a comment line
start:
set x = 1
if    x goto end
print never

end:
print x
"""
    assert TinyProgramRepositoryDB.are_sources_equivalent(source_a, source_b)


def test_compare_tiny_sources_cli(tmp_path):
    same_a = tmp_path / "same_a.tiny"
    same_b = tmp_path / "same_b.tiny"
    diff = tmp_path / "diff.tiny"

    same_a.write_text("start:\nprint hi\n", encoding="utf-8")
    same_b.write_text("\nstart:\nprint hi\n", encoding="utf-8")
    diff.write_text("start:\nprint bye\n", encoding="utf-8")

    same_result = subprocess.run(
        [sys.executable, "tools/compare_tiny_sources.py", str(same_a), str(same_b)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert same_result.returncode == 0
    assert "EQUIVALENT" in same_result.stdout

    diff_result = subprocess.run(
        [sys.executable, "tools/compare_tiny_sources.py", str(same_a), str(diff)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert diff_result.returncode == 1
    assert "DIFFERENT" in diff_result.stdout


def test_find_equivalent_program_id_uses_normalized_signature(tmp_path):
    db = TinyProgramRepositoryDB(tmp_path / "equivalent.db")
    db.initialize_schema()
    source_a = """
start:
set x=1
print x
"""
    source_b = """
start:
set x = 1
print x
"""
    first_program_id = db.register_program("first", source_a)
    found = db.find_equivalent_program_id(source_b)
    assert found == first_program_id
    db.close()
