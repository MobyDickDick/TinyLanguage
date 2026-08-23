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
