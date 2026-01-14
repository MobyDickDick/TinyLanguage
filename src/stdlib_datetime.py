"""Python-backed helpers for the TinyLanguage stdlib datetime module."""
from __future__ import annotations

import datetime as py_datetime


def datetime_isoformat(year: int, month: int, day: int, hour: int, minute: int, second: int) -> str:
    """Return ISO 8601 string for the provided datetime components."""
    return py_datetime.datetime(year, month, day, hour, minute, second).isoformat()


def date_isoformat(year: int, month: int, day: int) -> str:
    """Return ISO 8601 string for the provided date components."""
    return py_datetime.date(year, month, day).isoformat()


def time_isoformat(hour: int, minute: int, second: int) -> str:
    """Return ISO 8601 string for the provided time components."""
    return py_datetime.time(hour, minute, second).isoformat()


def timedelta_total_seconds(days: int, seconds: int) -> float:
    """Return total seconds for the provided timedelta components."""
    return py_datetime.timedelta(days=days, seconds=seconds).total_seconds()
