"""Test helpers shared across the suite.

This module re-exports the utility functions defined in ``tests/detailtests/utils.py``
so they can be imported consistently from ``tests.utils``.
"""

from tests.detailtests.utils import execute_tiny_program, run_tiny

__all__ = ["execute_tiny_program", "run_tiny"]
