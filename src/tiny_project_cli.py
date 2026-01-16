"""Project scaffolding helpers for TinyLanguage tooling.

Use this module to create a new TinyLanguage project layout, including
optionally generating VS Code debug configurations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


DEFAULT_ENTRY = "src/main.tiny"


def _default_runtime_path() -> str:
    runtime_path = Path(__file__).resolve().parent / "tiny_language.py"
    return str(runtime_path)


def _write_text(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise SystemExit(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: Dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise SystemExit(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _main_source(project_name: str) -> str:
    return (
        "// TinyLanguage starter program\n"
        f"print(\"Hello from {project_name}!\");\n"
    )


def init_project(
    root: Path,
    *,
    name: str | None,
    include_vscode: bool,
    force: bool,
    python_path: str,
    runtime_path: str | None,
) -> None:
    project_name = name or root.name
    manifest = {
        "name": project_name,
        "entry": DEFAULT_ENTRY,
        "deps": [],
    }
    _write_json(root / "module.json", manifest, force=force)
    _write_text(root / DEFAULT_ENTRY, _main_source(project_name), force=force)

    if include_vscode:
        launch_config = {
            "version": "0.2.0",
            "configurations": [
                {
                    "name": "TinyLanguage: Launch main.tiny",
                    "type": "tinylanguage",
                    "request": "launch",
                    "program": "${workspaceFolder}/src/main.tiny",
                    "runtime": "${config:tinylanguage.runtimePath}",
                    "python": "${config:tinylanguage.pythonPath}",
                    "stopOnEntry": False,
                }
            ],
        }
        settings = {
            "tinylanguage.pythonPath": python_path,
            "tinylanguage.runtimePath": runtime_path or _default_runtime_path(),
        }
        _write_json(root / ".vscode" / "launch.json", launch_config, force=force)
        _write_json(root / ".vscode" / "settings.json", settings, force=force)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a new TinyLanguage project")
    init_parser.add_argument("path", type=Path, help="Directory to create the project in")
    init_parser.add_argument("--name", help="Override the project name used in module.json")
    init_parser.add_argument(
        "--vscode",
        action="store_true",
        help="Generate VS Code launch + settings scaffolding",
    )
    init_parser.add_argument(
        "--python",
        default="python",
        dest="python_path",
        help="Python executable for VS Code settings (default: python)",
    )
    init_parser.add_argument(
        "--runtime",
        dest="runtime_path",
        help="Path to tiny_language.py for VS Code settings",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files if they already exist",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        init_project(
            args.path,
            name=args.name,
            include_vscode=args.vscode,
            force=args.force,
            python_path=args.python_path,
            runtime_path=args.runtime_path,
        )
    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
