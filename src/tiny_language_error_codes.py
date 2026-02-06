"""Machine-readable error codes and shared classification helpers.

This module centralizes runtime-facing error codes so interpreter, native VM,
and tooling backends can emit consistent metadata. The classification helper is
intentionally lightweight: it derives a stable code and optional hint from a
human-readable message without rewriting the message itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ErrorCodeInfo:
    """Describe a stable TinyLanguage error code."""

    code: str
    title: str
    description: str


ERROR_CODES: Dict[str, ErrorCodeInfo] = {
    "E000": ErrorCodeInfo("E000", "General error", "Fallback code when no specific category matches."),
    "E001": ErrorCodeInfo(
        "E001",
        "Return value must be bound",
        "A call or mutation requires binding the returned value to preserve updates.",
    ),
    "E002": ErrorCodeInfo("E002", "Unused binding", "A declared binding is never referenced."),
    "E003": ErrorCodeInfo("E003", "Unknown variable", "The referenced variable is not defined in scope."),
    "E004": ErrorCodeInfo(
        "E004",
        "Invalid exponent",
        "Exponentiation requires integer exponents or non-negative bases for fractional exponents.",
    ),
    "E005": ErrorCodeInfo("E005", "Invalid len target", "len expects a sized value."),
    "E006": ErrorCodeInfo(
        "E006",
        "Destructuring mismatch",
        "Destructuring calls must bind each output value explicitly.",
    ),
    "E008": ErrorCodeInfo("E008", "Module resolution error", "The module could not be resolved or imported."),
    "E009": ErrorCodeInfo("E009", "Type mismatch", "The provided value does not match the expected type."),
    "E010": ErrorCodeInfo("E010", "Missing return", "Not all code paths return a value."),
}


def error_info(code: str) -> Optional[ErrorCodeInfo]:
    """Return metadata for a known error code."""

    return ERROR_CODES.get(code)


def _closest_match(name: str, candidates: List[str]) -> Optional[str]:
    if not candidates:
        return None
    import difflib

    matches = difflib.get_close_matches(name, candidates, n=1, cutoff=0.6)
    return matches[0] if matches else None


def classify_error(msg: str, candidates: Optional[List[str]] = None) -> Tuple[str, Optional[str]]:
    """Infer a stable error code and hint from a message."""

    lower_msg = msg.lower()
    if "return value must be bound" in lower_msg or "must be returned" in lower_msg:
        return (
            "E001",
            "Bind the return value, e.g. `def result = call();`, or add a return that includes the mutated data.",
        )
    if lower_msg.startswith("unused"):
        return "E002", "Remove the unused binding or reference it."
    if "unknown variable" in lower_msg:
        suggestion = _closest_match(msg.split()[-1], candidates or []) if candidates is not None else None
        base_hint = "Declare the variable first, e.g. `def name = ...;`."
        if suggestion:
            return "E003", f"Did you mean `{suggestion}`? {base_hint}"
        return "E003", base_hint
    if "exponent for ^ must be an integer" in lower_msg:
        return "E004", "Use an integer exponent (cast with `int(...)` if necessary) when using the ^ operator."
    if "fractional exponent for ^ requires a non-negative base" in lower_msg:
        return "E004", "Use a non-negative base or an integer exponent when using the ^ operator."
    if "len expects a sized value" in lower_msg:
        return "E005", "Pass a list, string, heap pointer, or other sized value to `len`."
    if "destructuring call" in lower_msg and "must include output" in lower_msg:
        return "E006", "Add the missing binding(s) to the destructuring pattern so each referenced argument is captured."
    if "type mismatch" in lower_msg:
        return "E009", "Adjust the annotation or the provided value so they agree."
    if "not all paths" in lower_msg and "return" in lower_msg:
        return "E010", "Add return statements for every branch or supply a default return value."
    return "E000", None
