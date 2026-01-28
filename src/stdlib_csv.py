"""Python-backed helpers for the TinyLanguage stdlib csv module."""
from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence


def _validate_single_char(value: str, label: str) -> str:
    """Ensure delimiter/quote values are single-character strings."""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a single character")
    if len(value) != 1:
        raise ValueError(f"{label} must be a single character")
    return value


def _normalize_newlines(text: str) -> str:
    """Normalize Windows newlines to \n for deterministic parsing."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized.endswith("\n"):
        normalized = normalized[:-1]
    return normalized


def parse(
    text: str,
    delimiter: str,
    quote: str,
    has_header: bool,
) -> list:
    """Parse CSV text into lists or dicts, depending on header usage."""
    delimiter = _validate_single_char(delimiter, "delimiter")
    quote = _validate_single_char(quote, "quote")
    normalized = _normalize_newlines(text or "")
    if normalized == "":
        return []

    reader = csv.reader(io.StringIO(normalized), delimiter=delimiter, quotechar=quote)
    rows = [list(row) for row in reader]
    if not rows:
        return []

    if has_header:
        headers = rows[0]
        output = []
        for row in rows[1:]:
            row_map = {}
            for idx, header in enumerate(headers):
                row_map[header] = row[idx] if idx < len(row) else None
            output.append(row_map)
        return output

    return rows


def _stringify_value(value: object) -> str:
    """Convert cell values to strings, using empty strings for nulls."""
    if value is None:
        return ""
    return str(value)


def stringify(
    rows: Sequence,
    headers: Sequence | None,
    delimiter: str,
    quote: str,
) -> str:
    """Serialize rows into CSV text with deterministic ordering."""
    delimiter = _validate_single_char(delimiter, "delimiter")
    quote = _validate_single_char(quote, "quote")
    output = io.StringIO()
    writer = csv.writer(output, delimiter=delimiter, quotechar=quote, lineterminator="\n")

    if headers is not None:
        header_list = list(headers)
        writer.writerow([_stringify_value(h) for h in header_list])
        for row in rows or []:
            if not isinstance(row, Mapping):
                raise ValueError("rows must be dictionaries when headers are provided")
            writer.writerow([
                _stringify_value(row.get(header)) for header in header_list
            ])
    else:
        for row in rows or []:
            if isinstance(row, Mapping):
                raise ValueError("headers must be provided for dictionary rows")
            if isinstance(row, (str, bytes)):
                raise ValueError("row values must be sequences, not scalars")
            if not isinstance(row, Sequence):
                raise ValueError("row values must be sequences")
            writer.writerow([_stringify_value(value) for value in row])

    value = output.getvalue()
    if value.endswith("\n"):
        value = value[:-1]
    return value
