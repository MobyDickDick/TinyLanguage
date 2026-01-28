"""CLI stubs for the TinyLanguage package manager workflow.

These commands are intentionally lightweight placeholders that document the
expected UX for future package tooling. They currently focus on wiring and
guardrails, leaving dependency resolution and registry operations for later
implementation phases.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from tiny_pkg_resolution import write_lockfile


_DEFAULT_TEMPLATE = """\
[package]
name = "your-package-name"
version = "0.1.0"
description = "One-line summary of the package."
license = "MIT"
authors = ["Your Name <you@example.com>"]
homepage = "https://example.com"
repository = "https://github.com/your-org/your-package-name"

[dependencies]
# Example versioned dependency:
# http = "^1.2"
# Example local path dependency:
# config = { path = "../config" }
# Example registry override:
# json = { version = "~0.9", registry = "https://registry.tiny-lang.org" }

[dev-dependencies]
# test-utils = "^0.3"

[build-dependencies]
# codegen = { version = ">=1.0 <2.0" }

[registries]
default = "https://registry.tiny-lang.org"
"""


def _load_template() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    template_path = repo_root / "docs" / "tiny_pkg_init_template.toml"
    if template_path.is_file():
        return template_path.read_text(encoding="utf-8")
    return _DEFAULT_TEMPLATE


def _write_manifest(target: Path, *, force: bool) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    manifest_path = target / "tiny.toml"
    if manifest_path.exists() and not force:
        raise SystemExit(f"Refusing to overwrite existing manifest: {manifest_path}")
    manifest_path.write_text(_load_template(), encoding="utf-8")
    return manifest_path


def _cmd_init(args: argparse.Namespace) -> int:
    manifest_path = _write_manifest(Path(args.path).resolve(), force=args.force)
    print(f"Created {manifest_path}")
    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    dep_label = args.dependency
    if args.path:
        dep_label = f"{dep_label} (path: {args.path})"
    print(f"[stub] tiny pkg add {dep_label} - dependency resolution not implemented yet.")
    return 0


def _cmd_resolve(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.is_file():
        raise SystemExit(f"Missing manifest: {manifest_path}")
    lock_path = manifest_path.parent / "tiny.lock"
    write_lockfile(lock_path, manifest_path)
    print(f"Resolved dependencies into {lock_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TinyLanguage package tooling (stub)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a tiny.toml manifest")
    init_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory where tiny.toml should be created (default: current directory)",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite tiny.toml if it already exists",
    )
    init_parser.set_defaults(func=_cmd_init)

    add_parser = subparsers.add_parser("add", help="Add a dependency (stub)")
    add_parser.add_argument(
        "dependency",
        help="Dependency identifier, e.g. name@1.2.3 (stub only)",
    )
    add_parser.add_argument(
        "--path",
        help="Optional local path override (stub only)",
    )
    add_parser.set_defaults(func=_cmd_add)

    resolve_parser = subparsers.add_parser("resolve", help="Resolve dependencies")
    resolve_parser.add_argument(
        "--manifest",
        default="tiny.toml",
        help="Path to the tiny.toml manifest (default: ./tiny.toml)",
    )
    resolve_parser.set_defaults(func=_cmd_resolve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
