from pathlib import Path

from tiny_program_daemon import TinyProgramDaemon, TinyProgramGenerator
from tiny_program_repository_db_adapter import TinyProgramRepositoryDB


def test_generator_creates_requested_idea_file(tmp_path: Path):
    generator = TinyProgramGenerator(tmp_path, seed=7)

    generated = generator.create_program(slug="nand-gate")

    assert generated.exists()
    assert generated.name.endswith("_nand-gate.tiny")
    content = generated.read_text(encoding="utf-8")
    assert "Auto-generated Tiny program: Boolean NAND gate demo" in content


def test_daemon_run_forever_respects_max_runs(tmp_path: Path):
    generator = TinyProgramGenerator(tmp_path, seed=11)
    daemon = TinyProgramDaemon(generator, interval_seconds=0)

    produced = daemon.run_forever(max_runs=2)

    assert len(produced) == 2
    for path in produced:
        assert path.exists()
        assert path.suffix == ".tiny"


def test_generator_persists_program_to_repository_db(tmp_path: Path):
    db = TinyProgramRepositoryDB(tmp_path / "repo.db")
    db.initialize_schema()
    generator = TinyProgramGenerator(tmp_path, seed=7, repository_db=db)

    generated = generator.create_program(slug="linear-equation")
    source = generated.read_text(encoding="utf-8")
    program_id = db.find_equivalent_program_id(source)

    assert program_id is not None
    db.close()


def test_generator_rejects_duplicate_program_insert(tmp_path: Path):
    db = TinyProgramRepositoryDB(tmp_path / "repo.db")
    db.initialize_schema()
    generator = TinyProgramGenerator(tmp_path, seed=7, repository_db=db)

    generator.create_program(slug="nand-gate")

    try:
        generator.create_program(slug="nand-gate")
    except ValueError as exc:
        assert "already exists in DB" in str(exc)
    else:
        raise AssertionError("Expected duplicate insertion to be rejected")
    db.close()


def test_validator_accepts_loop_with_induction_variable_progress():
    report = TinyProgramGenerator.validate_program(
        """def i = 0;
while (i < 3) {
    if (i == 1) {
        def _unused = print(i);
    }
    i = i + 1;
}
def _unused_result = print(i);
"""
    )

    assert "loop_termination_unproven" not in {issue.code for issue in report.issues}


def test_validator_rejects_loop_without_condition_progress():
    report = TinyProgramGenerator.validate_program(
        """def i = 0;
def total = 0;
while (i < 3) {
    total = total + 1;
}
def _unused_i = print(i);
def _unused_total = print(total);
"""
    )

    assert "loop_termination_unproven" in {issue.code for issue in report.issues}


def test_validator_recognizes_spaced_literal_infinite_loop_once():
    report = TinyProgramGenerator.validate_program("while ( true ) {\n}\n")

    codes = [issue.code for issue in report.issues]
    assert codes.count("infinite_loop_literal") == 1
    assert "loop_termination_unproven" not in codes


def test_validator_accepts_divisor_after_returning_zero_guard():
    report = TinyProgramGenerator.validate_program(
        """fn divide(value, divisor) {
    if (divisor == 0) {
        return null;
    }
    return value / divisor;
}
"""
    )

    assert "division_nonzero_unproven" not in {issue.code for issue in report.issues}


def test_validator_rejects_divisor_without_nonzero_evidence():
    report = TinyProgramGenerator.validate_program(
        """fn divide(value, divisor) {
    return value / divisor;
}
"""
    )

    assert "division_nonzero_unproven" in {issue.code for issue in report.issues}


def test_validator_rejects_reassignment_after_zero_guard():
    report = TinyProgramGenerator.validate_program(
        """fn divide(value, divisor) {
    if (divisor == 0) {
        return null;
    }
    divisor = 0;
    return value / divisor;
}
"""
    )

    codes = [issue.code for issue in report.issues]
    assert codes.count("division_nonzero_unproven") == 1
