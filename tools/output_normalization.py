#!/usr/bin/env python3
"""Normalize backend output for parity testing."""

from __future__ import annotations

from dataclasses import dataclass
import pathlib
import re
from typing import Iterable

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]

BANNER_PREFIXES = (
    "tinylanguage",
    "tinyc",
    "tiny-language",
    "interpreter",
    "c backend",
    "llvm backend",
    "native vm",
)

TIMING_PATTERNS = (
    re.compile(r"\btime\s*="),
    re.compile(r"\belapsed\b"),
    re.compile(r"\b\d+(?:\.\d+)?\s*(ms|ns|s)\b"),
)

PID_PATTERNS = (
    re.compile(r"\b(pid|port)\s*[:=]\s*\d+\b", re.IGNORECASE),
    re.compile(r"\b(pid|port)\s+\d+\b", re.IGNORECASE),
)

SEED_PATTERNS = (
    re.compile(r"\b(seed|random_seed)\s*[:=]\s*\d+\b", re.IGNORECASE),
    re.compile(r"\b(seed|random_seed)\s+\d+\b", re.IGNORECASE),
)

ERROR_PREFIX = re.compile(r"^(?P<prefix>error|runtimeerror|typeerror)\s*[:\-]\s*", re.IGNORECASE)
WARNING_PREFIX = re.compile(r"^(?P<prefix>warning|warn)\s*[:\-]\s*", re.IGNORECASE)


@dataclass(frozen=True)
class NormalizationOptions:
    """Options that control how output normalization is applied."""

    root: pathlib.Path = PROJECT_ROOT
    keep_stack_traces: bool = False


def _strip_banners(lines: Iterable[str]) -> list[str]:
    """Remove version banners and backend headers."""
    filtered: list[str] = []
    for line in lines:
        lower = line.strip().lower()
        if any(lower.startswith(prefix) for prefix in BANNER_PREFIXES):
            continue
        filtered.append(line)
    return filtered


def _strip_timing(lines: Iterable[str]) -> list[str]:
    """Remove timing/perf lines entirely."""
    filtered: list[str] = []
    for line in lines:
        if any(pattern.search(line) for pattern in TIMING_PATTERNS):
            continue
        filtered.append(line)
    return filtered


def _replace_paths(text: str, root: pathlib.Path) -> str:
    """Replace absolute paths rooted at the repository with <ROOT> placeholders."""
    root_str = str(root)
    if not root_str.endswith("/"):
        root_str += "/"
    return text.replace(root_str, "<ROOT>/")


def _replace_ids(text: str) -> str:
    """Replace PID/port/seed values with placeholders."""
    for pattern in PID_PATTERNS:
        text = pattern.sub(lambda m: f"{m.group(1)}=<ID>", text)
    for pattern in SEED_PATTERNS:
        text = pattern.sub(lambda m: f"{m.group(1)}=<SEED>", text)
    return text


def _normalize_prefixes(line: str) -> str:
    """Normalize error and warning prefixes."""
    line = ERROR_PREFIX.sub("error: ", line)
    line = WARNING_PREFIX.sub("warning: ", line)
    return line


def _strip_stack_traces(lines: Iterable[str]) -> list[str]:
    """Remove stack trace lines."""
    filtered: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("Traceback"):
            continue
        if stripped.startswith("File ") or stripped.startswith("File \""):
            continue
        if stripped.startswith("Stack trace"):
            continue
        filtered.append(line)
    return filtered


def _collapse_blank_lines(lines: Iterable[str]) -> list[str]:
    """Collapse multiple blank lines into a single blank line."""
    collapsed: list[str] = []
    previous_blank = False
    for line in lines:
        blank = line == ""
        if blank and previous_blank:
            continue
        collapsed.append(line)
        previous_blank = blank
    return collapsed


def normalize_output(text: str, options: NormalizationOptions | None = None) -> str:
    """Normalize output text according to the parity spec."""
    if options is None:
        options = NormalizationOptions()

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]

    lines = _strip_banners(lines)
    lines = _strip_timing(lines)
    if not options.keep_stack_traces:
        lines = _strip_stack_traces(lines)

    rebuilt = "\n".join(lines)
    rebuilt = _replace_paths(rebuilt, options.root)
    rebuilt = _replace_ids(rebuilt)

    lines = [_normalize_prefixes(line) for line in rebuilt.split("\n")]
    lines = _collapse_blank_lines(lines)

    return "\n".join(lines).strip("\n")
