import sys
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parent
sys.path.append(str(TESTS_ROOT))

from utils import execute_tiny_program, run_tiny


@pytest.fixture
def run_program():
    """Run a TinyLanguage program via the CLI and capture output."""

    return execute_tiny_program


@pytest.fixture
def run_tiny_source():
    """Compile and run TinyLanguage source in-process for convenience."""

    return run_tiny
