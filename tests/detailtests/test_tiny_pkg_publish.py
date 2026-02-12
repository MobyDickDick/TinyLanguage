"""Regression coverage for the publish dry-run staging helper."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tiny_pkg_resolution import manifest_hash_for_path


def _write_manifest_and_lock(project_dir: Path) -> None:
    manifest_path = project_dir / "tiny.toml"
    manifest_path.write_text(
        """[package]
name = \"demo\"
version = \"1.2.3\"
""",
        encoding="utf-8",
    )
    lock_path = project_dir / "tiny.lock"
    lock_path.write_text(
        f'manifest_hash = "{manifest_hash_for_path(manifest_path)}"\n',
        encoding="utf-8",
    )


def test_publish_requires_explicit_dry_run_flag(tmp_path: Path) -> None:
    """The helper should fail fast when run without ``--dry-run``."""

    _write_manifest_and_lock(tmp_path)
    script = Path(__file__).resolve().parents[2] / "tools" / "tiny_pkg_publish.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Only dry-run publishing is currently implemented" in result.stderr


def test_publish_dry_run_stages_expected_artifacts(tmp_path: Path) -> None:
    """``--dry-run`` should stage the tarball + metadata payload."""

    _write_manifest_and_lock(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.tiny").write_text('print("hello")\n', encoding="utf-8")

    script = Path(__file__).resolve().parents[2] / "tools" / "tiny_pkg_publish.py"
    result = subprocess.run(
        [sys.executable, str(script), "--dry-run"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Dry-run publish payload staged." in result.stdout

    publish_dir = tmp_path / "publish"
    assert (publish_dir / "demo-1.2.3.tar.gz").is_file()
    assert (publish_dir / "demo-1.2.3.json").is_file()
    assert (publish_dir / "manifest.json").is_file()
