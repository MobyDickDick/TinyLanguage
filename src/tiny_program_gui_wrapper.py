"""Generate a read-only GUI for the result of an approved sandbox run.

The wrapper deliberately displays the captured, byte-verified output instead of
executing the imported program again.  This preserves the sandbox boundary when
someone opens the optional desktop presentation.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


GUI_POLICY = "tiny-source-gui-wrapper-v1"
REQUIRED_SANDBOX_POLICY = "tiny-source-sandbox-v1"


@dataclass(frozen=True)
class GuiWrapperReport:
    policy: str
    source_file: str
    source_sha256: str
    sandbox_report_file: str
    sandbox_output_file: str
    sandbox_output_sha256: str
    wrapper_file: str
    wrapper_sha256: str
    status: str
    generated_at: str
    next_stage: None


def _regular_file(path: Path, description: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{description} must be a regular file without symlinks")


def _approved_result(
    program: Path, sandbox_report: Path, sandbox_output: Path
) -> tuple[bytes, bytes]:
    """Return bytes only when all three artifacts form one passing hand-off."""
    _regular_file(program, "program")
    _regular_file(sandbox_report, "sandbox report")
    _regular_file(sandbox_output, "sandbox output")
    try:
        report = json.loads(sandbox_report.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("sandbox report must be valid UTF-8 JSON") from exc
    source = program.read_bytes()
    output = sandbox_output.read_bytes()
    valid = (
        isinstance(report, dict)
        and report.get("policy") == REQUIRED_SANDBOX_POLICY
        and report.get("verdict") == "passed"
        and report.get("next_stage") == "gui-wrapper"
        and report.get("source_file") == program.name
        and report.get("source_sha256") == hashlib.sha256(source).hexdigest()
        and report.get("output_sha256") == hashlib.sha256(output).hexdigest()
        and report.get("output_bytes") == len(output)
    )
    if not valid:
        raise ValueError("sandbox report does not approve these exact artifacts")
    return source, output


def _wrapper_source(title: str, output: bytes) -> bytes:
    encoded = base64.b64encode(output).decode("ascii")
    source = f'''"""Read-only presentation of a TinyLanguage sandbox result."""
import base64
import tkinter as tk

TITLE = {title!r}
OUTPUT = base64.b64decode({encoded!r}).decode("utf-8", errors="replace")


def main():
    root = tk.Tk()
    root.title(TITLE)
    text = tk.Text(root, wrap="word", width=80, height=24)
    text.insert("1.0", OUTPUT)
    text.configure(state="disabled")
    text.pack(fill="both", expand=True)
    tk.Button(root, text="Close", command=root.destroy).pack(pady=8)
    root.mainloop()


if __name__ == "__main__":
    main()
'''
    return source.encode("utf-8")


def generate_gui_wrapper(
    program: Path,
    sandbox_report: Path,
    sandbox_output: Path,
    destination_dir: Path,
) -> tuple[Path, Path]:
    """Create a Tk wrapper and a provenance report for one passing result."""
    source, output = _approved_result(program, sandbox_report, sandbox_output)
    destination_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    wrapper_path = destination_dir / f"{program.stem}_gui.py"
    report_path = destination_dir / f"{program.stem}.gui.json"
    wrapper = _wrapper_source(f"TinyLanguage: {program.stem}", output)
    wrapper_path.write_bytes(wrapper)
    os.chmod(wrapper_path, 0o700)
    report = GuiWrapperReport(
        policy=GUI_POLICY,
        source_file=program.name,
        source_sha256=hashlib.sha256(source).hexdigest(),
        sandbox_report_file=sandbox_report.name,
        sandbox_output_file=sandbox_output.name,
        sandbox_output_sha256=hashlib.sha256(output).hexdigest(),
        wrapper_file=wrapper_path.name,
        wrapper_sha256=hashlib.sha256(wrapper).hexdigest(),
        status="generated-read-only",
        generated_at=datetime.now(timezone.utc).isoformat(),
        next_stage=None,
    )
    report_path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
    os.chmod(report_path, 0o600)
    return wrapper_path, report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("program", type=Path)
    parser.add_argument("sandbox_report", type=Path)
    parser.add_argument("sandbox_output", type=Path)
    parser.add_argument("--destination", type=Path, default=Path("var/gui-wrappers"))
    args = parser.parse_args(argv)
    wrapper, report = generate_gui_wrapper(
        args.program, args.sandbox_report, args.sandbox_output, args.destination
    )
    print(f"GUI wrapper: {wrapper}")
    print(f"GUI report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
