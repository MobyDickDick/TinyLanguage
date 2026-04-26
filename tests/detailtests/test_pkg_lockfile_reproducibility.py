"""Regression coverage for cross-platform deterministic lockfile rendering."""

from __future__ import annotations

from pathlib import Path

from tiny_pkg_resolution import write_lockfile


def _write_dependency(root: Path, rel_path: str, *, version: str) -> None:
    dep_path = root / Path(rel_path)
    dep_path.mkdir(parents=True, exist_ok=True)
    (dep_path / "tiny.toml").write_text(
        "\n".join(
            [
                "[package]",
                f'name = "{dep_path.name}"',
                f'version = "{version}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (dep_path / "README.md").write_text(f"{dep_path.name}\n", encoding="utf-8")


def test_write_lockfile_normalizes_windows_path_separator(tmp_path: Path) -> None:
    _write_dependency(tmp_path, "deps/alpha", version="1.0.0")
    manifest_path = tmp_path / "tiny.toml"
    manifest_path.write_text(
        "\n".join(
            [
                "[package]",
                'name = "demo"',
                'version = "0.1.0"',
                "",
                "[dependencies]",
                'alpha = { path = "deps\\\\alpha", version = "1.0.0" }',
                "",
            ]
        ),
        encoding="utf-8",
    )

    lock_path = tmp_path / "tiny.lock"
    write_lockfile(lock_path, manifest_path)

    lock_text = lock_path.read_text(encoding="utf-8")
    assert 'path = "deps/alpha"' in lock_text
    assert 'path = "deps\\\\alpha"' not in lock_text


def test_write_lockfile_sorts_dependencies_for_stable_output(tmp_path: Path) -> None:
    _write_dependency(tmp_path, "deps/alpha", version="1.0.0")
    _write_dependency(tmp_path, "deps/beta", version="2.0.0")

    manifest_path = tmp_path / "tiny.toml"
    manifest_path.write_text(
        "\n".join(
            [
                "[package]",
                'name = "demo"',
                'version = "0.1.0"',
                "",
                "[dependencies]",
                'beta = { path = "deps/beta", version = "2.0.0" }',
                'alpha = { path = "deps/alpha", version = "1.0.0" }',
                "",
            ]
        ),
        encoding="utf-8",
    )

    lock_path = tmp_path / "tiny.lock"
    write_lockfile(lock_path, manifest_path)

    names = [line for line in lock_path.read_text(encoding="utf-8").splitlines() if line.startswith('name = ')]
    assert names == ['name = "alpha"', 'name = "beta"']


def test_write_lockfile_preserves_toolchain_constraint(tmp_path: Path) -> None:
    _write_dependency(tmp_path, "deps/alpha", version="1.0.0")
    manifest_path = tmp_path / "tiny.toml"
    manifest_path.write_text(
        "\n".join(
            [
                "[package]",
                'name = "demo"',
                'version = "0.1.0"',
                'tiny_language = ">=1.2 <2.0"',
                "",
                "[dependencies]",
                'alpha = { path = "deps/alpha", version = "1.0.0" }',
                "",
            ]
        ),
        encoding="utf-8",
    )

    lock_path = tmp_path / "tiny.lock"
    write_lockfile(lock_path, manifest_path)

    lock_text = lock_path.read_text(encoding="utf-8")
    assert 'toolchain = ">=1.2 <2.0"' in lock_text
