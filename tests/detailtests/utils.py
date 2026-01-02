import os
import pathlib
import subprocess
import sys
import tempfile
from dataclasses import dataclass

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.append(str(SRC_ROOT))

from tiny_language import compile_and_run  # noqa: E402


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    returncode: int


def run_tiny(src: str) -> str:
    """Compile and run TinyLanguage source in-process, returning stdout.

    This mirrors the common pattern used across the test suite.
    """

    return compile_and_run(src)


def execute_tiny_program(
    source: str, *, timeout: float | None = None, args: list[str] | None = None, env: dict[str, str] | None = None
) -> ExecutionResult:
    """Execute a TinyLanguage program via the CLI.

    The source text is written to a temporary ``.tiny`` file, executed with
    ``python -m tiny_language`` and cleaned up afterwards. Stdout, stderr and
    the process return code are captured for assertions.
    """

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".tiny", delete=False, encoding="utf-8", dir=PROJECT_ROOT
        ) as tmp:
            tmp.write(source)
            tmp_path = pathlib.Path(tmp.name)

        proc = subprocess.run(
            [sys.executable, str(SRC_ROOT / "tiny_language.py"), str(tmp_path), *(args or [])],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=PROJECT_ROOT,
            env={
                **os.environ,
                **(env or {}),
                "PYTHONPATH": os.pathsep.join(
                    filter(None, [str(SRC_ROOT), os.environ.get("PYTHONPATH")])
                ),
            },
        )

        return ExecutionResult(proc.stdout, proc.stderr, proc.returncode)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
