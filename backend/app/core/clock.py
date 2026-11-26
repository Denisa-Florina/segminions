"""The application's notion of "now": always timezone-aware UTC.

`datetime.now()` returns local time without a timezone, which Firestore then stores as
if it were UTC, so every timestamp is off by the server's UTC offset. Use `utc_now`
instead, and accept a `Clock` where code needs to be tested at a controlled time.
"""

from collections.abc import Callable
from datetime import datetime, timezone

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | float | int | None) -> datetime | None:
    """Read a stored timestamp: a datetime (naive ones are UTC) or, as written by
    earlier versions, a Unix timestamp in seconds."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
