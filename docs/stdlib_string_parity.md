# stdlib.string parity map

This parity map enumerates the subset of Python's string APIs that TinyLanguage
mirrors today. Each entry lists the Python API and the corresponding
TinyLanguage function exposed by `stdlib.string` (a thin wrapper around the
native `String` namespace).

## Core functions

| Python string API | TinyLanguage `stdlib.string` | Notes |
| --- | --- | --- |
| `str.split(sep)` | `string.split(text, sep)` | Requires an explicit separator; no `maxsplit` or default whitespace splitting. |
| `sep.join(parts)` | `string.join(parts, sep)` | Expects a list of strings; returns a single string. |
| `substr in text` | `string.contains(text, needle)` | Boolean contains check (case-sensitive). |
| `str.upper()` | `string.upper(text)` | Uppercase transform for ASCII/Unicode codepoints as supported by the runtime. |
| `str.lower()` | `string.lower(text)` | Lowercase transform for ASCII/Unicode codepoints as supported by the runtime. |
| `str.strip()` | `string.strip(text)` | Trims leading/trailing whitespace; no custom character set parameter. |
| `str.lstrip()` | `string.lstrip(text)` | Trims leading whitespace only. |
| `str.rstrip()` | `string.rstrip(text)` | Trims trailing whitespace only. |
| `str.replace(old, new)` | `string.replace(text, old, replacement)` | Replaces all occurrences; no `count` parameter. |
| `str.startswith(prefix)` | `string.starts_with(text, prefix)` | Prefix check. |
| `str.endswith(suffix)` | `string.ends_with(text, suffix)` | Suffix check. |
| `str.isdigit()` | `string.is_digit(text)` | Returns `true` for numeric-only strings; aligns with TinyLanguage `String.is_digit`. |

## TinyLanguage-specific helpers

| TinyLanguage `stdlib.string` | Notes |
| --- | --- |
| `string.trim(text)` | Convenience alias for whitespace trimming; same behavior as `strip` in this module. |
| `string.repeat(text, count)` | Repeats a string `count` times; mirrors Python's `text * count` idiom. |

## Parity coverage notes

- The module is implemented in `stdlib/string.tiny` and delegates directly to
  the runtime `String` namespace. The API intentionally stays small and
  explicit: optional parameters like `maxsplit`, `sep=None`, or custom strip
  character sets are not available yet.
- When you need Python-style defaults (e.g., whitespace splitting), call
  `string.trim`/`string.strip` first and then `string.split` with an explicit
  separator.
