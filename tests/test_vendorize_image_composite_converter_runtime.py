from __future__ import annotations

from pathlib import Path

from tools.vendorize_image_composite_converter_runtime import _discover_import_roots, vendor_runtime


def test_discover_import_roots_finds_converter_dependencies(tmp_path: Path) -> None:
    src = tmp_path / "sample.py"
    src.write_text("import cv2\nimport numpy as np\nfrom fitz import open\n", encoding="utf-8")

    roots = _discover_import_roots(src)

    assert {"cv2", "numpy", "fitz"}.issubset(roots)


def test_vendor_runtime_copies_modules_and_writes_manifest(tmp_path: Path) -> None:
    source = tmp_path / "image_composite_converter.py"
    source.write_text("import cv2\nimport numpy\n", encoding="utf-8")

    venv = tmp_path / ".venv"
    site_packages = venv / "lib" / f"python3.{__import__('sys').version_info.minor}" / "site-packages"
    (site_packages / "cv2").mkdir(parents=True)
    (site_packages / "cv2" / "__init__.py").write_text("", encoding="utf-8")
    (site_packages / "numpy").mkdir(parents=True)
    (site_packages / "numpy" / "__init__.py").write_text("", encoding="utf-8")
    (site_packages / "numpy-1.0.dist-info").mkdir(parents=True)

    vendor_root = tmp_path / "vendor" / "converter_runtime"
    copied = vendor_runtime(source, venv, vendor_root, ("cv2", "numpy"))

    assert (vendor_root / "cv2" / "__init__.py").exists()
    assert (vendor_root / "numpy" / "__init__.py").exists()
    assert (vendor_root / "MANIFEST.txt").exists()
    assert any(path.endswith("numpy-1.0.dist-info") for path in copied)
