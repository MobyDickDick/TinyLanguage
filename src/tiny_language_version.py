"""Read the release version in an installed, source, or frozen runtime."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def runtime_version() -> str:
    root = Path(__file__).resolve().parent
    # Frozen bundles and source checkouts carry VERSION as an ordinary asset.
    for candidate in (root / "VERSION", root.parent / "VERSION"):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    try:
        return version("tinylanguage")
    except PackageNotFoundError:
        return "unknown"
