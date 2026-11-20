"""Time helpers. Storage is naive UTC; control-room rules (shift timings, D-3 windows, 00:00 revival deadline)
are evaluated in IST (UTC+05:30)."""
from datetime import date, datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def to_utc_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def utc_to_ist(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc).astimezone(IST)


def ist_to_utc_naive(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=IST).astimezone(timezone.utc).replace(tzinfo=None)


def now_ist() -> datetime:
    return datetime.now(IST)
