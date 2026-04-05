from pathlib import Path

from tiny_program_daemon import TinyProgramDaemon, TinyProgramGenerator


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
