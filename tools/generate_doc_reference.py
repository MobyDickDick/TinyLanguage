#!/usr/bin/env python3
"""Generate a Markdown reference from Python docstrings."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass(frozen=True)
class DocItem:
    """Represent a documented symbol extracted from a module."""

    kind: str
    name: str
    qualname: str
    docstring: str | None


@dataclass(frozen=True)
class ModuleDoc:
    """Capture a module's docstring and extracted documented items."""

    path: Path
    docstring: str | None
    items: List[DocItem]


def _iter_python_files(paths: Iterable[Path]) -> Iterable[Path]:
    """Yield Python files under the provided file system roots."""
    for path in paths:
        if path.is_dir():
            for file_path in path.rglob("*.py"):
                if file_path.name.startswith("."):
                    continue
                yield file_path
        elif path.is_file() and path.suffix == ".py":
            yield path


def _collect_module_docs(path: Path) -> ModuleDoc:
    """Parse a module and collect its top-level docstrings."""
    source = path.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(path))
    module_docstring = ast.get_docstring(module)
    items: List[DocItem] = []

    for node in module.body:
        if isinstance(node, ast.FunctionDef):
            items.append(
                DocItem(
                    kind="function",
                    name=node.name,
                    qualname=node.name,
                    docstring=ast.get_docstring(node),
                )
            )
        elif isinstance(node, ast.ClassDef):
            class_doc = ast.get_docstring(node)
            items.append(
                DocItem(
                    kind="class",
                    name=node.name,
                    qualname=node.name,
                    docstring=class_doc,
                )
            )
            for class_node in node.body:
                if isinstance(class_node, ast.FunctionDef):
                    items.append(
                        DocItem(
                            kind="method",
                            name=class_node.name,
                            qualname=f"{node.name}.{class_node.name}",
                            docstring=ast.get_docstring(class_node),
                        )
                    )

    return ModuleDoc(path=path, docstring=module_docstring, items=items)


def _format_docstring(docstring: str | None, indent: str = "") -> List[str]:
    """Format docstrings into Markdown-friendly lines with indentation."""
    if not docstring:
        return [f"{indent}*No docstring available.*"]
    return [f"{indent}{line}" for line in docstring.splitlines()]


def render_markdown(modules: Iterable[ModuleDoc]) -> str:
    """Render module documentation into a Markdown reference document."""
    lines: List[str] = [
        "# Generated reference",
        "",
        "This reference is generated from Python docstrings.",
        "",
    ]
    for module in modules:
        lines.append(f"## {module.path.as_posix()}")
        lines.append("")
        lines.extend(_format_docstring(module.docstring))
        lines.append("")

        if not module.items:
            lines.append("_No public classes or functions found._")
            lines.append("")
            continue

        for item in module.items:
            lines.append(f"### {item.kind}: `{item.qualname}`")
            lines.append("")
            lines.extend(_format_docstring(item.docstring, indent=""))
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    """Run the module entry point."""
    parser = argparse.ArgumentParser(
        description="Generate a Markdown reference from Python docstrings."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Files or directories to scan for Python modules.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the generated reference to this file instead of stdout.",
    )
    args = parser.parse_args()

    input_paths = [Path(path) for path in args.paths]
    modules = [_collect_module_docs(path) for path in _iter_python_files(input_paths)]
    modules.sort(key=lambda module: module.path.as_posix())

    content = render_markdown(modules)
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
