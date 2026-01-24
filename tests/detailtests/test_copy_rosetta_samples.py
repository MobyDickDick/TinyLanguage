"""Tests for copying Rosetta samples tooling."""

import importlib.util
from pathlib import Path


def _load_copy_module():
    """Import the rosetta copy module from the examples folder."""
    module_path = Path(__file__).resolve().parents[2] / "examples" / "rosetta" / "copy_rosetta_samples.py"
    spec = importlib.util.spec_from_file_location("copy_rosetta_samples", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_filter_missing_accepts_prefix_filters(tmp_path):
    """Ensure prefix filters select the expected missing files."""
    module = _load_copy_module()
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()

    for name in ("alpha.py", "beta.py", "gamma.py"):
        (source / name).write_text("# sample", encoding="utf-8")
    (dest / "alpha.py").write_text("# already present", encoding="utf-8")

    missing = module.list_missing(source, dest)
    filtered = module.filter_missing(missing, ["ga", "be"])

    assert [path.stem for path in filtered] == ["beta", "gamma"]


def test_copy_batch_supports_dry_run(tmp_path):
    """Verify dry-run mode does not write files."""
    module = _load_copy_module()
    dest = tmp_path / "dest"
    dest.mkdir()

    files = []
    for name in ("first.py", "second.py"):
        path = tmp_path / name
        path.write_text("# source", encoding="utf-8")
        files.append(path)

    copied = module.copy_batch(files, dest, limit=1, delay=0.0, dry_run=True)

    assert len(copied) == 1
    assert not (dest / "first.py").exists()
    assert not (dest / "second.py").exists()


def test_main_triggers_transpiler_when_requested(monkeypatch, tmp_path):
    """Confirm the CLI triggers the transpiler when flags are set."""
    module = _load_copy_module()
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    tiny_dest = tmp_path / "tiny"
    source.mkdir()
    (source / "hello.py").write_text("print('hi')", encoding="utf-8")

    invoked = {}

    def _fake_run(dest_path: Path, *, source_dir: Path):
        invoked["dest"] = dest_path
        invoked["source"] = source_dir

    monkeypatch.setattr(module, "run_transpiler", _fake_run)

    exit_code = module.main(
        [
            str(dest),
            "--source",
            str(source),
            "--limit",
            "5",
            "--delay",
            "0",
            "--transpile",
            "--transpile-dest",
            str(tiny_dest),
        ]
    )

    assert exit_code == 0
    assert invoked["dest"] == tiny_dest
    assert invoked["source"] == source
    assert (dest / "hello.py").exists()
