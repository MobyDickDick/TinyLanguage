# stdlib.datetime parity map

This parity map enumerates the subset of Python's `datetime` module that
TinyLanguage mirrors today. Each entry lists the Python API and the
corresponding TinyLanguage function exposed by `stdlib.datetime`.

## Formatting helpers

| Python `datetime` | TinyLanguage `stdlib.datetime` | Notes |
| --- | --- | --- |
| `datetime.datetime(year, month, day, hour, minute, second).isoformat()` | `datetime.datetime_isoformat(year, month, day, hour, minute, second)` | Returns `YYYY-MM-DDTHH:MM:SS`. |
| `datetime.date(year, month, day).isoformat()` | `datetime.date_isoformat(year, month, day)` | Returns `YYYY-MM-DD`. |
| `datetime.time(hour, minute, second).isoformat()` | `datetime.time_isoformat(hour, minute, second)` | Returns `HH:MM:SS`. |
| `datetime.timedelta(days=..., seconds=...).total_seconds()` | `datetime.total_seconds(days, seconds)` | Returns floating-point seconds. |

## Parsing helpers

| Python `datetime` | TinyLanguage `stdlib.datetime` | Notes |
| --- | --- | --- |
| `datetime.datetime.fromisoformat(value)` | `datetime.datetime_parse_iso(value)` | Returns `[year, month, day, hour, minute, second]`. |
| `datetime.date.fromisoformat(value)` | `datetime.date_parse_iso(value)` | Returns `[year, month, day]`. |
| `datetime.time.fromisoformat(value)` | `datetime.time_parse_iso(value)` | Returns `[hour, minute, second]`. |

## Parity coverage notes

- Snapshot tests for ISO parsing and formatting live in `tests/spec/` and
  validate stdout against fixed expectations.
