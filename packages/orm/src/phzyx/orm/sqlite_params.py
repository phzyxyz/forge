"""SQLite bind-parameter adaptation.

Python 3.12+ deprecated the default sqlite3 adapters for datetime/date/time.
Convert those values to ISO strings before binding so both sync (sqlite3) and
async (aiosqlite) paths stay warning-free and consistent.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any


def adapt_sqlite_params(params: list[Any]) -> list[Any]:
    """Return bind values safe for sqlite3 / aiosqlite.

    Non-temporal values pass through unchanged. ``datetime``, ``date``, and
    ``time`` become ISO-8601 strings via ``.isoformat()``.

    Args:
        params: Positional SQL parameters (``?`` placeholders).

    Returns:
        A new list suitable for ``connection.execute(sql, params)``.
    """
    out: list[Any] = []
    for value in params:
        if isinstance(value, (datetime, date, time)):
            out.append(value.isoformat())
        else:
            out.append(value)
    return out
