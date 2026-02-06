"""Module resolution helpers for TinyLanguage runtime imports.

The runtime keeps the import resolver isolated here so the core evaluator can
focus on execution semantics, while module lookup and caching remain reusable
across interpreters and tooling entry points.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from tiny_errors import SourcePos, SourceSpan, StackFrame, TinyLangError
from tiny_language_module_resolution import ModuleResolutionConfig, candidate_module_paths, resolve_module_name


@dataclass
class NamespaceRef:
    """Reference to a lazily loaded namespace registered by the runtime."""

    runtime: "Runtime"
    name: str


def _import_binding_name(module: str, alias: Optional[str]) -> str:
    """Return the binding name for an import statement."""

    if alias:
        return alias
    stripped = module.lstrip(".") or module
    return stripped.split(".")[-1]


class ModuleResolver:
    """Locate and load TinyLanguage modules from configurable search roots.

    The resolver accepts optional search paths (including the ``TINYPATH``
    environment variable) and memoizes successfully loaded modules so repeated
    imports are cheap. It also guards against circular imports by tracking the
    current resolution stack.
    """

    def __init__(self, search_paths: Optional[List[Path]] = None):
        self._config = ModuleResolutionConfig.from_search_paths(search_paths)
        self.stdlib_root = self._config.stdlib_root
        self.search_paths = self._config.search_paths
        self.cache: Dict[Path, NamespaceRef] = {}
        self._in_progress: List[Path] = []

    def _resolve_name(self, raw: str, caller_namespace: Optional[str], pos: Optional[object]) -> str:
        """Normalize relative import names against the caller's namespace."""

        return resolve_module_name(raw, caller_namespace, pos)

    def _candidate_paths(self, module_name: str, caller_path: Optional[Path]) -> List[Path]:
        """Return possible filesystem paths for a module name."""

        return candidate_module_paths(
            module_name,
            caller_path=caller_path,
            config=self._config,
        )

    def import_module(
        self,
        name: str,
        runtime: "Runtime",
        *,
        caller_namespace: Optional[str],
        caller_path: Optional[Path],
        pos: Optional[Any] = None,
    ) -> NamespaceRef:
        """Import a module, executing it if necessary and caching the namespace."""

        from tiny_language_runtime import Environment, compile_and_run

        resolved_name = self._resolve_name(name, caller_namespace, pos)
        pos_for_error = pos.start if isinstance(pos, SourceSpan) else pos
        frame_pos = pos_for_error or SourcePos.origin()
        for candidate in self._candidate_paths(resolved_name, caller_path):
            resolved_path = candidate.resolve()
            if resolved_path in self.cache:
                return self.cache[resolved_path]
            if resolved_path.exists():
                if resolved_path in self._in_progress:
                    raise TinyLangError(
                        f"circular import involving {resolved_path}",
                        pos_for_error or SourcePos.origin(),
                        code="E008",
                        span=pos if isinstance(pos, SourceSpan) else None,
                    )
                self._in_progress.append(resolved_path)
                module_frame: Optional[StackFrame] = None
                if runtime.debugger is not None:
                    module_frame = StackFrame(resolved_name or "<module>", resolved_name, frame_pos)
                    runtime.call_stack.append(module_frame)
                try:
                    module_env = Environment(parent=None, namespace=resolved_name, runtime=runtime)
                    previous_global_env = runtime.global_env
                    try:
                        compile_and_run(
                            resolved_path.read_text(encoding="utf-8"),
                            env=module_env,
                            runtime=runtime,
                            module_namespace=resolved_name,
                            module_path=resolved_path,
                            module_resolver=self,
                        )
                    finally:
                        runtime.global_env = previous_global_env
                    ns_ref = NamespaceRef(runtime, resolved_name)
                    self.cache[resolved_path] = ns_ref
                    return ns_ref
                finally:
                    if module_frame is not None:
                        runtime.call_stack.pop()
                    self._in_progress.remove(resolved_path)
        raise TinyLangError(
            f"module '{name}' not found on search path",
            pos or SourcePos.origin(),
            code="E008",
            span=pos if isinstance(pos, SourceSpan) else None,
        )
