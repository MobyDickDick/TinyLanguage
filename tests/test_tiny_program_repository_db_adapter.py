"""Tests for the Tiny program repository SQLite adapter."""

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
