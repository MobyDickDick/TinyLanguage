"""Keep the high-level TinyCPU roadmap aligned with its acceptance checklist."""

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).parents[2]


def test_expansion_roadmap_does_not_reopen_completed_electrical_packages():
    """A completed AP must not remain advertised as the next work package."""

    detailed = (REPOSITORY_ROOT / "docs" / "tiny_cpu_roadmap.md").read_text(
        encoding="utf-8"
    )
    expansion = (REPOSITORY_ROOT / "docs" / "expansion_roadmap.md").read_text(
        encoding="utf-8"
    )

    for package in range(9, 13):
        assert re.search(rf"^- \[x\] \*\*AP {package}:\*\*", detailed, re.MULTILINE)

    tinycpu_section = expansion.split("## 1) Native compiler", maxsplit=1)[0]
    assert "**Completed boundary**: AP 9 through AP 12" in tinycpu_section
    assert "**Next package**: none is currently scoped" in tinycpu_section
    assert "add a mandatory headless" not in tinycpu_section


def test_active_backlog_agrees_that_no_tinycpu_package_is_scoped():
    """Do not claim an empty roadmap while retaining an unchecked CPU task."""

    active_tasks = (REPOSITORY_ROOT / "docs" / "open_tasks.md").read_text(
        encoding="utf-8"
    ).split("## Open-task audit", maxsplit=1)[0]
    expansion = (REPOSITORY_ROOT / "docs" / "expansion_roadmap.md").read_text(
        encoding="utf-8"
    )

    unchecked_tinycpu = re.findall(
        r"^- \[ \] \*\*[^\n]*(?:TinyCPU|Tiny CPU)[^\n]*",
        active_tasks,
        re.IGNORECASE | re.MULTILINE,
    )
    assert unchecked_tinycpu == []

    tinycpu_section = expansion.split("## 1) Native compiler", maxsplit=1)[0]
    assert "**Next package**: none is currently scoped" in tinycpu_section
    assert "Reconcile stale TinyCPU follow-up notes" in active_tasks
    assert "Freeze the restored TinyCPU jump-operand route" in active_tasks
    assert "Freeze TinyCPU next-PC selector net isolation" in active_tasks

    user_guide = (REPOSITORY_ROOT / "docs" / "tiny_cpu.md").read_text(
        encoding="utf-8"
    )
    hardware_readme = (
        REPOSITORY_ROOT / "hardware" / "logisim" / "README.md"
    ).read_text(encoding="utf-8")
    detailed = (REPOSITORY_ROOT / "docs" / "tiny_cpu_roadmap.md").read_text(
        encoding="utf-8"
    )
    stale_completion_claims = (
        "Assembler erzeugt noch **kein binäres ROM-Abbild**",
        "weiterhin sichtbare, zu kurze Schleifenausführung",
        "Als nächster externer Abnahmeschritt bleibt",
    )
    combined_docs = user_guide + hardware_readme + detailed
    for claim in stale_completion_claims:
        assert claim not in combined_docs


def test_detailed_hardware_docs_do_not_advertise_completed_follow_ups():
    """Historical implementation notes must not look like active packages."""

    detailed = (REPOSITORY_ROOT / "docs" / "tiny_cpu_roadmap.md").read_text(
        encoding="utf-8"
    )
    hardware_readme = (
        REPOSITORY_ROOT / "hardware" / "logisim" / "README.md"
    ).read_text(encoding="utf-8")

    assert "## Abgeschlossenes Folgepaket:" in detailed
    assert "## Folgepaket:" not in detailed

    stale_markers = (
        "The next integration step is",
        "The non-binary data paths are next",
        "Als nächster binärer\nOperationsschritt",
        "bleibt das folgende Arbeitspaket",
        "noch offen sind",
    )
    combined_docs = detailed + hardware_readme
    for marker in stale_markers:
        assert marker not in combined_docs
