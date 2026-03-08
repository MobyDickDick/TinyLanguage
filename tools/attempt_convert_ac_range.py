#!/usr/bin/env python3
"""Attempt conversion for a reference range and write reproducible logs.

This helper is designed for environments where conversion dependencies may be
missing. It always writes:
- a machine-readable JSON report
- a human-readable Markdown log that can be committed to the repository
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import importlib.metadata
import importlib.machinery
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_ROOT.parent
DEFAULT_VENDOR_RUNTIME = REPO_ROOT / "vendor" / "converter_runtime"


def _vendor_runtime_compatible(runtime_root: Path) -> bool:
    """Return True when vendored native extensions match this Python ABI."""
    if not runtime_root.exists():
        return False

    extension_suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    runtime_packages = ("numpy", "cv2", "fitz")

    for package in runtime_packages:
        package_root = runtime_root / package
        if not package_root.exists():
            continue

        for binary in package_root.rglob("*"):
            if not binary.is_file() or binary.suffix.lower() not in {".so", ".pyd"}:
                continue
            if binary.name.endswith(extension_suffixes):
                continue
            return False

    return True


def _vendor_runtime_importable(runtime_root: Path) -> bool:
    """Return True when runtime can import required native deps in-process."""
    runtime = str(runtime_root)
    if not runtime:
        return False

    old_sys_path = list(sys.path)
    old_pythonpath = os.environ.get("PYTHONPATH", "")
    try:
        sys.path.insert(0, runtime)
        os.environ["PYTHONPATH"] = runtime if not old_pythonpath else f"{runtime}{os.pathsep}{old_pythonpath}"
        import numpy  # noqa: F401
        import cv2  # noqa: F401
        import fitz  # noqa: F401
    except Exception:
        return False
    finally:
        sys.path[:] = old_sys_path
        if old_pythonpath:
            os.environ["PYTHONPATH"] = old_pythonpath
        else:
            os.environ.pop("PYTHONPATH", None)

    return True


def _apply_runtime_path_to_sys_path(runtime_path: str) -> None:
    if not runtime_path:
        return
    if runtime_path not in sys.path:
        sys.path.append(runtime_path)


def _probe_mod(name: str) -> dict[str, str | bool]:
    spec = importlib.util.find_spec(name)
    out: dict[str, str | bool] = {
        "available": spec is not None,
        "origin": "",
        "version": "",
    }
    if spec is None:
        return out

    out["origin"] = str(spec.origin or "")
    try:
        out["version"] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        out["version"] = "unknown"
    return out


def _collect_inputs(folder: Path, start: str, end: str) -> list[str]:
    pattern = re.compile(r"^(AC\d{4})(?:_[LMS])?\.(?:bmp|jpg|png)$", re.IGNORECASE)

    def parse_ref(ref: str) -> tuple[str, int]:
        m = re.match(r"^([A-Z]{2})(\d{4})$", ref.upper())
        if not m:
            raise ValueError(f"Invalid ref: {ref}")
        return m.group(1), int(m.group(2))

    p_start, n_start = parse_ref(start)
    p_end, n_end = parse_ref(end)
    if p_start != p_end:
        raise ValueError("Start and end prefix must match (example: AC0800..AC0884)")

    out: list[str] = []
    for name in sorted(os.listdir(folder)):
        m = pattern.match(name)
        if not m:
            continue
        prefix = m.group(1)[:2].upper()
        number = int(m.group(1)[2:])
        if prefix == p_start and n_start <= number <= n_end:
            out.append(name)
    return out


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _write_markdown_log(log_path: Path, report: dict) -> None:
    env = report["environment"]
    deps = report["dependencies"]
    conv = report["conversion"]

    runtime_path = str(report.get("runtime_path") or "")

    lines = [
        "# AC range conversion attempt log",
        "",
        f"- Timestamp (UTC): `{report['timestamp_utc']}`",
        f"- Range: `{report['range']['start']}..{report['range']['end']}`",
        f"- Iterations: `{report['iterations']}`",
        f"- Input count: `{report['input_count']}`",
        "",
        "## Environment",
        "",
        f"- Python: `{env['python_version']}`",
        f"- Executable: `{env['python_executable']}`",
        f"- Platform: `{env['platform']}`",
        f"- Runtime path override: `{runtime_path or '(none)'}`",
        "",
        "## Dependencies",
        "",
        f"- cv2: available=`{deps['cv2']['available']}` version=`{deps['cv2']['version']}` origin=`{deps['cv2']['origin']}`",
        f"- numpy: available=`{deps['numpy']['available']}` version=`{deps['numpy']['version']}` origin=`{deps['numpy']['origin']}`",
        f"- fitz: available=`{deps['fitz']['available']}` version=`{deps['fitz']['version']}` origin=`{deps['fitz']['origin']}`",
        "",
        "## Command",
        "",
        "```bash",
        conv["command"],
        "```",
        "",
    ]

    if conv["ran"]:
        lines.extend(
            [
                "## Result",
                "",
                f"- Ran conversion: `true`",
                f"- Exit code: `{conv['exit_code']}`",
                f"- Duration (s): `{conv['duration_seconds']}`",
                "",
                "### Converter stdout",
                "",
                "```text",
                conv["stdout"].rstrip(),
                "```",
                "",
                "### Converter stderr",
                "",
                "```text",
                conv["stderr"].rstrip(),
                "```",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Result",
                "",
                "- Ran conversion: `false`",
                f"- Reason: `{conv['reason']}`",
                "",
                "## Suggested install commands",
                "",
                "### Linux/macOS (bash)",
                "```bash",
                "python3 -m venv .venv",
                "source .venv/bin/activate",
                "python -m pip install --upgrade pip",
                "python -m pip install numpy opencv-python-headless pymupdf",
                "```",
                "",
                "### Windows (PowerShell)",
                "```powershell",
                "py -3.12 -m venv .venv",
                ".\\.venv\\Scripts\\Activate.ps1",
                "python -m pip install --upgrade pip",
                "python -m pip install numpy opencv-python-headless pymupdf",
                "```",
            ]
        )

    log_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _resolve_runtime_path(cli_runtime_path: str) -> str:
    """Resolve runtime path preference with repo-local vendor fallback."""
    explicit = str(cli_runtime_path or "").strip()
    if explicit:
        explicit_path = Path(explicit)
        if explicit_path.exists() and _vendor_runtime_importable(explicit_path):
            return explicit
        return ""
    if _vendor_runtime_compatible(DEFAULT_VENDOR_RUNTIME) and _vendor_runtime_importable(DEFAULT_VENDOR_RUNTIME):
        return str(DEFAULT_VENDOR_RUNTIME)
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", default="artifacts/images_to_convert")
    parser.add_argument("--csv", default="artifacts/images_to_convert/nonexistent.csv")
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--start", default="AC0800")
    parser.add_argument("--end", default="AC0884")
    parser.add_argument(
        "--runtime-path",
        default="",
        help=(
            "Optional path to a staged runtime directory (containing cv2/numpy/fitz). If omitted, the script auto-uses vendor/converter_runtime when present. "
            "Will be prepended to PYTHONPATH for dependency checks and conversion run."
        ),
    )
    parser.add_argument(
        "--runtime-zip",
        default="",
        help=(
            "Optional zip archive containing staged runtime libs (cv2/numpy/fitz at archive root). "
            "When set, it is extracted to a temporary directory and used as runtime path."
        ),
    )
    parser.add_argument(
        "--report",
        default="artifacts/converted_symbols/AC0800_AC0884_attempt_report.json",
        help="JSON output report path",
    )
    parser.add_argument(
        "--log",
        default="artifacts/converted_symbols/AC0800_AC0884_attempt_log.md",
        help="Markdown output log path",
    )
    args = parser.parse_args()

    runtime_path = _resolve_runtime_path(args.runtime_path)
    runtime_zip = args.runtime_zip.strip()
    temp_runtime_dir: str | None = None
    if runtime_zip:
        zpath = Path(runtime_zip)
        if not zpath.exists():
            raise FileNotFoundError(f"Runtime zip not found: {runtime_zip}")
        temp_runtime_dir = tempfile.mkdtemp(prefix="converter_runtime_")
        with zipfile.ZipFile(zpath, "r") as zf:
            zf.extractall(temp_runtime_dir)
        runtime_path = temp_runtime_dir

    _apply_runtime_path_to_sys_path(runtime_path)

    images_dir = Path(args.images)
    report_path = Path(args.report)
    log_path = Path(args.log)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    inputs = _collect_inputs(images_dir, args.start, args.end)
    deps = {name: _probe_mod(name) for name in ("cv2", "numpy", "fitz")}

    cmd = [
        sys.executable,
        "src/image_composite_converter.py",
        str(images_dir),
        args.csv,
        str(args.iterations),
        "--start",
        args.start,
        "--end",
        args.end,
    ]
    cmd_str = " ".join(cmd)

    conversion = {
        "ran": False,
        "reason": "missing dependencies",
        "command": cmd_str,
        "exit_code": None,
        "duration_seconds": 0.0,
        "stdout": "",
        "stderr": "",
    }

    dep_ok = all(bool(deps[name]["available"]) for name in ("cv2", "numpy", "fitz"))
    if dep_ok:
        started = dt.datetime.now(dt.timezone.utc)
        env = os.environ.copy()
        if runtime_path:
            old_pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = runtime_path if not old_pythonpath else f"{runtime_path}{os.pathsep}{old_pythonpath}"
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
        finished = dt.datetime.now(dt.timezone.utc)
        duration = (finished - started).total_seconds()
        conversion = {
            "ran": True,
            "reason": "executed",
            "command": cmd_str,
            "exit_code": proc.returncode,
            "duration_seconds": round(duration, 3),
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }

    report = {
        "timestamp_utc": _now(),
        "range": {"start": args.start, "end": args.end},
        "iterations": args.iterations,
        "input_count": len(inputs),
        "inputs": inputs,
        "environment": {
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
            "platform": platform.platform(),
        },
        "dependencies": deps,
        "runtime_path": runtime_path,
        "runtime_zip": runtime_zip,
        "conversion": conversion,
    }

    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown_log(log_path, report)

    if temp_runtime_dir:
        import shutil

        shutil.rmtree(temp_runtime_dir, ignore_errors=True)

    print(f"Wrote report: {report_path}")
    print(f"Wrote log: {log_path}")

    if not conversion["ran"]:
        print("Conversion skipped (dependencies missing). See Markdown log for install hints.")
        return 0
    return 0 if conversion["exit_code"] == 0 else int(conversion["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
