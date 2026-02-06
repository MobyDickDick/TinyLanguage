"""Edge-case coverage for shared module-resolution helpers."""

from pathlib import Path

import pytest

from tiny_language_module_resolution import (
    ModuleResolutionConfig,
    candidate_module_paths,
    resolve_module_name,
)


def test_relative_import_rejects_missing_namespace():
    """Relative imports require a caller namespace to anchor the path."""

    with pytest.raises(Exception) as excinfo:
        resolve_module_name(".helpers", None, None)

    assert "relative import outside" in str(excinfo.value)


def test_relative_import_rejects_overflow():
    """Relative imports cannot traverse beyond the namespace root."""

    with pytest.raises(Exception) as excinfo:
        resolve_module_name("...utils", "app.core", None)

    assert "relative import traverses beyond" in str(excinfo.value)


def test_stdlib_resolution_isolated_and_ordered(tmp_path):
    """Stdlib resolution only consults the stdlib root in a stable order."""

    stdlib_root = tmp_path / "stdlib"
    stdlib_root.mkdir()
    config = ModuleResolutionConfig(
        search_paths=[tmp_path / "local"],
        stdlib_root=stdlib_root,
        project_root=None,
    )

    candidates = candidate_module_paths("std.io", caller_path=None, config=config)

    assert candidates == [
        stdlib_root / "io.tiny",
        stdlib_root / "io" / "__init__.tiny",
    ]


def test_pkg_resolution_prefers_lockfile_vendor_roots(tmp_path):
    """Pkg imports resolve via lockfile entries and vendor roots first."""

    project_root = tmp_path / "project"
    project_root.mkdir()
    lockfile = project_root / "tiny.lock"
    lockfile.write_text(
        """
lockfile_version = 1

[[dependencies]]
name = "widgets"
version = "1.2.3"
source = "registry"
registry = "https://registry.example.com"
checksum = "deadbeef"
""".lstrip(),
        encoding="utf-8",
    )

    vendor_root = project_root / "vendor" / "registry.example.com" / "widgets" / "1.2.3"
    (vendor_root / "src").mkdir(parents=True)

    config = ModuleResolutionConfig(
        search_paths=[project_root],
        stdlib_root=tmp_path / "stdlib",
        project_root=project_root,
    )

    candidates = candidate_module_paths("pkg.widgets.client", caller_path=None, config=config)

    assert candidates == [
        vendor_root / "src" / "client.tiny",
        vendor_root / "src" / "client" / "__init__.tiny",
        vendor_root / "client.tiny",
        vendor_root / "client" / "__init__.tiny",
    ]
