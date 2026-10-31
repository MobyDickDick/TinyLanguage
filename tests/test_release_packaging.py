"""Regression coverage for release identity, metadata and installed assets."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_builder", ROOT / "tools/release/build_release_artifacts.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def test_source_release_is_reproducible_and_has_valid_checksums(tmp_path, monkeypatch):
    """Changing output directories must not change retained artifact bytes."""
    monkeypatch.chdir(ROOT)
    outputs = [tmp_path / "first", tmp_path / "second"]
    for output in outputs:
        args = argparse.Namespace(version=None, tag=None, output_dir=str(output),
                                  sign=False, gpg_key_id=None)
        assert release.build_release(args) == 0
        for line in (output / "SHA256SUMS").read_text().splitlines():
            checksum, name = line.split("  ")
            assert release.sha256sum(output / name) == checksum
        metadata = json.loads((output / "build-info.json").read_text())
        assert metadata["build"]["reproducibility_verified"] is False
        assert all("path" not in artifact for artifact in metadata["artifacts"])
    for name in ("SHA256SUMS", "TinyLanguage-v1.0.0.tar.gz", "TinyLanguage-v1.0.0-sbom.spdx.json"):
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()


def test_vsix_normalization_removes_zip_metadata(tmp_path):
    """Entry order, host mode bits and timestamps must not change VSIX hashes."""
    paths = [tmp_path / "a.vsix", tmp_path / "b.vsix"]
    for index, path in enumerate(paths):
        with zipfile.ZipFile(path, "w") as archive:
            for name in (["b", "a"] if index == 0 else ["a", "b"]):
                info = zipfile.ZipInfo(name, (2020 + index, 1, 1, 0, 0, 0))
                info.external_attr = index << 16
                archive.writestr(info, name.encode())
        release.normalize_vsix(path, 1793232000)
    assert paths[0].read_bytes() == paths[1].read_bytes()


@pytest.mark.skipif(os.name == "nt", reason="Executable permission bits require POSIX")
@pytest.mark.parametrize("artifact_source", ["built", "included"])
def test_release_preserves_executable_permissions(tmp_path, monkeypatch, artifact_source):
    """Retained executables must run outside the checkout after artifact copying."""
    monkeypatch.chdir(ROOT)
    name = "tiny-language-linux-x86_64"

    def make_executable(directory):
        directory.mkdir(parents=True, exist_ok=True)
        executable = directory / name
        executable.write_text('#!/bin/sh\nprintf "TinyLanguage 1.0.0\\n"\n', encoding="utf-8")
        executable.chmod(0o755)
        return executable

    def fake_build(source, destination, **kwargs):
        return [make_executable(destination)]

    monkeypatch.setattr(release, "build_from_archive", fake_build)
    included = [str(make_executable(tmp_path / "supplied"))] if artifact_source == "included" else []
    output = tmp_path / "release"
    args = argparse.Namespace(
        version=None, tag=None, output_dir=str(output), sign=False, gpg_key_id=None,
        binary=artifact_source == "built", include_artifact=included,
        verify_reproducible=artifact_source == "built",
    )

    assert release.build_release(args) == 0
    executable = output / name
    assert stat.S_IMODE(executable.stat().st_mode) == 0o755
    result = subprocess.run([str(executable), "--version"], cwd=tmp_path,
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "TinyLanguage 1.0.0"
    assert result.stderr == ""
    checksums = dict(line.split("  ") for line in (output / "SHA256SUMS").read_text().splitlines())
    assert checksums[release.sha256sum(executable)] == name


def test_import_and_stdlib_do_not_require_generated_source(tmp_path):
    """A minimal installed layout must work with no stitched file to import."""
    import shutil

    installed = tmp_path / "installed"
    installed.mkdir()
    for path in (ROOT / "src").glob("*.py"):
        if path.name != "tiny_language_stitched.py":
            shutil.copyfile(path, installed / path.name)
    shutil.copytree(ROOT / "src/stdlib", installed / "stdlib", ignore=shutil.ignore_patterns("__pycache__"))
    for path in (ROOT / "stdlib").glob("*.tiny"):
        shutil.copyfile(path, installed / "stdlib" / path.name)
    environment = {**os.environ, "PYTHONPATH": str(installed), "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-c", """
import linecache
from pathlib import Path
import tiny_language
output = tiny_language.compile_and_run('import stdlib.math as m; print(m.sqrt(81));', stream_output=False)
assert output.strip() == '9'
generated = Path(tiny_language.__file__).parent / 'tiny_language_stitched.py'
assert not generated.exists()
assert linecache.getlines(str(generated))
"""], cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr


def test_sbom_records_build_dependencies():
    payload = release.generate_spdx([], "1.0.0", "commit", epoch=1793232000,
                                    dependencies=[{"name": "setuptools", "version": "84.1.0"}])
    assert payload["creationInfo"]["created"] == "2026-10-29T00:00:00Z"
    assert payload["packages"][0]["name"] == "setuptools"
    assert payload["packages"][0]["versionInfo"] == "84.1.0"


def test_cli_reports_release_version_outside_checkout(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "src/tiny_language_cli.py"), "--version"],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "TinyLanguage " + (ROOT / "VERSION").read_text().strip()


def test_python_build_from_archived_sources_produces_both_formats(tmp_path):
    """Exercise the actual build hooks, including source assets and entry points."""
    source = tmp_path / "source.tar.gz"
    paths = [Path(name) for name in ("pyproject.toml", "setup.py", "MANIFEST.in",
                                    "VERSION", "README.md", "CHANGELOG.md", "tools/packaging_backend.py")]
    paths += list(Path("src").glob("*.py")) + list(Path("src/stdlib").glob("*.py"))
    paths += list(Path("stdlib").glob("*.tiny")) + list(Path("src_tiny").glob("*.tiny"))
    with tarfile.open(source, "w:gz") as archive:
        for path in paths:
            if path.name != "tiny_language_stitched.py":
                archive.add(ROOT / path, arcname=path.as_posix())
    first = release.build_from_archive(source, tmp_path / "first", python=True,
                                       binary=False, vsix=False, epoch=1793232000)
    second = release.build_from_archive(source, tmp_path / "second", python=True,
                                        binary=False, vsix=False, epoch=1793232000)
    assert {p.name: release.sha256sum(p) for p in first} == {
        p.name: release.sha256sum(p) for p in second}
    wheel = next(path for path in first if path.suffix == ".whl")
    assert any(path.name.endswith(".tar.gz") for path in first)
    with zipfile.ZipFile(wheel) as archive:
        assert "stdlib/math.tiny" in archive.namelist()
        assert "src_tiny/tiny_language_parser.tiny" in archive.namelist()
        assert "tiny_language_runtime.py" in archive.namelist()
        assert "tiny_language_stitched.py" not in archive.namelist()
        entry_points = archive.read("tinylanguage-1.0.0.dist-info/entry_points.txt").decode()
        assert "tiny = tiny_language_cli:main" in entry_points
