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
