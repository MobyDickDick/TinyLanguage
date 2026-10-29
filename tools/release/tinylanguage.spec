# PyInstaller executes spec files as Python. Resolve paths from SPEC, not cwd.
from pathlib import Path

root = Path(SPEC).resolve().parents[2]
sources = sorted((root / "src").glob("*.py"))
sources = [path for path in sources if path.stem != "tiny_language_stitched"]
datas = [(str(path), ".") for path in sources]
datas.append((str(root / "VERSION"), "."))
datas += [(str(path), "stdlib") for path in sorted((root / "stdlib").glob("*.tiny"))]
datas += [(str(path), "src_tiny") for path in sorted((root / "src_tiny").glob("*.tiny"))]
analysis = Analysis(
    [str(root / "tools/release/standalone_entry.py")],
    pathex=[str(root / "src")],
    datas=datas,
    hiddenimports=[path.stem for path in sources] + ["stdlib"],
    excludes=["pytest", "setuptools", "pip"],
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, analysis.binaries, analysis.datas,
          name="tiny-language", console=True, upx=False, strip=False)
