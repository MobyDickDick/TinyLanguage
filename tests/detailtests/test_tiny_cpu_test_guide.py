"""Regression checks for the beginner-facing TinyCPU test instructions."""

from pathlib import Path


REPOSITORY = Path(__file__).parents[2]
GUIDE = REPOSITORY / "docs" / "tiny_cpu_test_guide.md"


def test_tiny_cpu_test_guide_names_runnable_repository_entry_points() -> None:
    text = GUIDE.read_text(encoding="utf-8")

    required_references = (
        "hardware/logisim/TinyCPU.circ",
        "scripts/test-logisim.sh",
        "scripts/test-logisim-local.sh",
        "src/tiny_cpu_logisim.py",
        "artifacts/tinycpu-ap12-acceptance/acceptance.json",
    )
    for reference in required_references:
        assert reference in text

    for relative_path in (
        "hardware/logisim/TinyCPU.circ",
        "scripts/test-logisim.sh",
        "scripts/test-logisim-local.sh",
        "src/tiny_cpu_logisim.py",
    ):
        assert (REPOSITORY / relative_path).is_file()


def test_primary_docs_link_to_the_self_test_guide() -> None:
    readme = (REPOSITORY / "README.md").read_text(encoding="utf-8")
    cpu_docs = (REPOSITORY / "docs" / "tiny_cpu.md").read_text(encoding="utf-8")

    assert "docs/tiny_cpu_test_guide.md" in readme
    assert "tiny_cpu_test_guide.md" in cpu_docs
