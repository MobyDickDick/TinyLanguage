"""Package the existing public modules and their runtime source assets."""

from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildRuntime(build_py):
    """Keep Tiny stdlib modules beside the Python stdlib registry in wheels."""

    def run(self):
        super().run()
        destination = Path(self.build_lib) / "stdlib"
        destination.mkdir(parents=True, exist_ok=True)
        for source in sorted(Path("stdlib").glob("*.tiny")):
            shutil.copyfile(source, destination / source.name)


setup(
    version=Path("VERSION").read_text(encoding="utf-8").strip(),
    py_modules=sorted(
        path.stem for path in Path("src").glob("*.py")
        if path.stem != "tiny_language_stitched"
    ),
    packages=["stdlib", "src_tiny"],
    package_dir={"": "src", "src_tiny": "src_tiny"},
    package_data={"src_tiny": ["*.tiny"]},
    include_package_data=False,
    cmdclass={"build_py": BuildRuntime},
)
