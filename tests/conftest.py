import pytest

from tests.utils import execute_tiny_program, run_tiny


@pytest.fixture
def run_program():
    """Run a TinyLanguage program via the CLI and capture output."""

    return execute_tiny_program


@pytest.fixture
def run_tiny_source():
    """Compile and run TinyLanguage source in-process for convenience."""

    return run_tiny
