from __future__ import annotations

from pathlib import Path

from src.converter_runtime_bootstrap import configure_converter_runtime, main


def test_configure_converter_runtime_returns_none_for_missing_path(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    assert configure_converter_runtime(missing) is None


def test_bootstrap_main_runs_script_with_forwarded_args(tmp_path: Path, capsys) -> None:
    vendor_root = tmp_path / "vendor" / "converter_runtime"
    vendor_root.mkdir(parents=True)

    script = tmp_path / "echo_args.py"
    script.write_text(
        "import sys\n"
        "print('ARGS=' + ','.join(sys.argv[1:]))\n",
        encoding="utf-8",
    )

    exit_code = main([
        "--vendor-root",
        str(vendor_root),
        "--run-script",
        str(script),
        "--",
        "--input",
        "image.png",
    ])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Runtime-Pfad aktiviert" in out
    assert "ARGS=--input,image.png" in out


def test_configure_converter_runtime_appends_vendor_to_sys_path(tmp_path: Path) -> None:
    import sys

    vendor_root = tmp_path / "vendor" / "converter_runtime"
    vendor_root.mkdir(parents=True)

    original = list(sys.path)
    try:
        configured = configure_converter_runtime(vendor_root)
        assert configured == vendor_root.resolve()
        assert sys.path[-1] == str(vendor_root.resolve())
    finally:
        sys.path[:] = original
