"""Python module wrapper for running the TinyLanguage CLI via ``python -m tiny_language``.

Running TinyLanguage as a module is convenient, but the main interpreter lives in
``src/tiny_language.py``. This shim ensures that invoking ``python -m tiny_language``
behaves the same as executing the source file directly.
"""
from __future__ import annotations

from pathlib import Path
import importlib.util
import sys


repo_root = Path(__file__).resolve().parent
src_entrypoint = repo_root / "src" / "tiny_language.py"

# Ensure bundled modules (e.g., tiny_errors.py) are importable even when the project
# is not installed as a package.
src_dir = src_entrypoint.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))


def _load_impl():
    if not src_entrypoint.is_file():
        raise ImportError("Cannot find src/tiny_language.py; run from the repository root.")

    spec = importlib.util.spec_from_file_location("_tiny_language_impl", src_entrypoint)
    if spec is None or spec.loader is None:
        raise ImportError("Failed to load TinyLanguage implementation module.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_IMPL = _load_impl()

# Export the public API from the implementation module so "import tiny_language" works.
__all__ = list(getattr(_IMPL, "__all__", []) or [n for n in dir(_IMPL) if not n.startswith("_")])
globals().update({name: getattr(_IMPL, name) for name in __all__})


def __getattr__(name):
    return getattr(_IMPL, name)


def __dir__():
    return sorted(set(list(globals().keys()) + list(dir(_IMPL))))


def _main() -> int:
    try:
        return int(_IMPL.main(sys.argv[1:]))
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":
    raise SystemExit(_main())
