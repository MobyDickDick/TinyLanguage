"""Tests for stdlib wrapper parity with runtime namespaces."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT / "src"))

from tiny_language import Environment, NamespaceRef, Runtime, register_stdlib  # noqa: E402


STDLIB_DIR = PROJECT_ROOT / "stdlib"
NAMESPACE_CALL_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*)\.([A-Za-z0-9_]+)\s*\(")


def _runtime_namespace_functions() -> dict[str, set[str]]:
    runtime = Runtime("")
    env = Environment(parent=None, namespace=None, runtime=runtime)
    runtime.global_env = env
    register_stdlib(runtime, env, NamespaceRef)

    namespaces: dict[str, set[str]] = defaultdict(set)
    for qualified in runtime.native_functions:
        if "." not in qualified:
            continue
        namespace, name = qualified.split(".", 1)
        namespaces[namespace].add(name)
    return namespaces


def _strip_line_comment(line: str) -> str:
    if "//" in line:
        return line.split("//", 1)[0]
    return line


def _stdlib_namespace_calls(path: Path) -> set[tuple[str, str]]:
    calls: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = _strip_line_comment(line)
        for namespace, func in NAMESPACE_CALL_RE.findall(clean):
            calls.add((namespace, func))
    return calls


def test_stdlib_wrappers_reference_runtime_namespaces() -> None:
    """Ensure stdlib wrappers only call functions registered in the runtime."""
    runtime_namespaces = _runtime_namespace_functions()
    missing: dict[str, list[str]] = defaultdict(list)

    for module_path in sorted(STDLIB_DIR.glob("*.tiny")):
        for namespace, func in _stdlib_namespace_calls(module_path):
            if namespace not in runtime_namespaces:
                missing[module_path.name].append(f"{namespace}.{func} (namespace missing)")
                continue
            if func not in runtime_namespaces[namespace]:
                missing[module_path.name].append(f"{namespace}.{func}")

    assert not missing, "Stdlib wrapper calls missing runtime helpers:\n" + "\n".join(
        f"{module}: {', '.join(sorted(entries))}" for module, entries in sorted(missing.items())
    )
