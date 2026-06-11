"""Regression coverage for cross-platform deterministic lockfile rendering."""

from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path

import pytest

from tiny_pkg_resolution import write_lockfile


if importlib.util.find_spec("tomllib"):
    tomllib = importlib.import_module("tomllib")
else:
    tomllib = importlib.import_module("tomli")


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


def test_write_lockfile_collapses_redundant_path_segments(tmp_path: Path) -> None:
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
                'alpha = { path = "./deps//nested/../alpha/", version = "1.0.0" }',
                "",
            ]
        ),
        encoding="utf-8",
    )

    lock_path = tmp_path / "tiny.lock"
    write_lockfile(lock_path, manifest_path)

    lock_data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    assert lock_data["dependencies"][0]["path"] == "deps/alpha"


def test_write_lockfile_normalizes_dependency_override_paths(tmp_path: Path) -> None:
    _write_dependency(tmp_path, "overrides/alpha", version="1.0.0")
    manifest_path = tmp_path / "tiny.toml"
    manifest_path.write_text(
        "\n".join(
            [
                "[package]",
                'name = "demo"',
                'version = "0.1.0"',
                "",
                "[dependencies]",
                'alpha = "1.0.0"',
                "",
                "[dependency-overrides]",
                "alpha = { path = '.\\overrides\\nested\\..\\alpha\\' }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    lock_path = tmp_path / "tiny.lock"
    write_lockfile(lock_path, manifest_path)

    lock_data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    assert lock_data["dependencies"][0]["path"] == "overrides/alpha"


def test_write_lockfile_escapes_path_as_valid_toml(tmp_path: Path) -> None:
    dependency_path = 'deps/quoted"library'
    _write_dependency(tmp_path, dependency_path, version="1.0.0")
    manifest_path = tmp_path / "tiny.toml"
    manifest_path.write_text(
        "\n".join(
            [
                "[package]",
                'name = "demo"',
                'version = "0.1.0"',
                "",
                "[dependencies]",
                f'alpha = {{ path = {json.dumps(dependency_path)}, version = "1.0.0" }}',
                "",
            ]
        ),
        encoding="utf-8",
    )

    lock_path = tmp_path / "tiny.lock"
    write_lockfile(lock_path, manifest_path)

    first_render = lock_path.read_bytes()
    lock_data = tomllib.loads(first_render.decode("utf-8"))
    assert lock_data["dependencies"][0]["path"] == dependency_path

    write_lockfile(lock_path, manifest_path)
    assert lock_path.read_bytes() == first_render
    assert first_render.endswith(b"\n")
    assert b"\r\n" not in first_render


@pytest.mark.parametrize("dependency_path", ["/opt/shared/alpha", "C:\\deps\\alpha"])
def test_write_lockfile_rejects_host_absolute_paths(
    tmp_path: Path, dependency_path: str
) -> None:
    manifest_path = tmp_path / "tiny.toml"
    manifest_path.write_text(
        "\n".join(
            [
                "[package]",
                'name = "demo"',
                'version = "0.1.0"',
                "",
                "[dependencies]",
                f'alpha = {{ path = {json.dumps(dependency_path)}, version = "1.0.0" }}',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="Dependency paths must be relative"):
        write_lockfile(tmp_path / "tiny.lock", manifest_path)
