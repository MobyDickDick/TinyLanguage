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
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path


def _has_mod(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


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
        "",
        "## Dependencies",
        "",
        f"- cv2: `{deps['cv2']}`",
        f"- numpy: `{deps['numpy']}`",
        f"- fitz: `{deps['fitz']}`",
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", default="artifacts/images_to_convert")
    parser.add_argument("--csv", default="artifacts/images_to_convert/nonexistent.csv")
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--start", default="AC0800")
    parser.add_argument("--end", default="AC0884")
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

    images_dir = Path(args.images)
    report_path = Path(args.report)
    log_path = Path(args.log)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    inputs = _collect_inputs(images_dir, args.start, args.end)
    deps = {name: _has_mod(name) for name in ("cv2", "numpy", "fitz")}

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

    if deps["cv2"] and deps["numpy"] and deps["fitz"]:
        started = dt.datetime.now(dt.timezone.utc)
        proc = subprocess.run(cmd, capture_output=True, text=True)
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
        "conversion": conversion,
    }

    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown_log(log_path, report)

    print(f"Wrote report: {report_path}")
    print(f"Wrote log: {log_path}")

    if not conversion["ran"]:
        print("Conversion skipped (dependencies missing). See Markdown log for install hints.")
        return 0
    return 0 if conversion["exit_code"] == 0 else int(conversion["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
