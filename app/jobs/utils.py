import logging
from collections.abc import Iterator
from datetime import datetime, time, timedelta, timezone
from typing import Any, TypeVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import settings

logger = logging.getLogger("finassist.jobs.utils")

T = TypeVar("T")


def get_safe_timezone(tz_name: str | None) -> ZoneInfo:
    """Return a valid ZoneInfo instance. Falls back to DEFAULT_TIMEZONE or UTC on error."""
    default_tz = settings.DEFAULT_TIMEZONE or "Asia/Kolkata"
    candidate = (tz_name or "").strip()

    if candidate:
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            logger.debug("Unknown timezone '%s', falling back to default '%s'", candidate, default_tz)

    try:
        return ZoneInfo(default_tz)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def is_briefing_due(
    briefing_time: time,
    user_tz_name: str | None,
    last_briefing_date: str | None,
    now_utc: datetime | None = None,
    window_minutes: int = 120,
) -> tuple[bool, str]:
    """
    Check if a daily briefing is due for a user at the given UTC time.

    Returns:
        tuple[bool, str]: (is_due, user_local_today_str)
        - is_due: True if the briefing should be dispatched now.
        - user_local_today_str: The YYYY-MM-DD date string in the user's local timezone.

    Rules:
        1. If user already received a briefing for today's local date (last_briefing_date == today), return False.
        2. If local time has not reached the scheduled briefing time today, return False.
        3. If local time is at or after scheduled time, and within the dispatch catch-up window, return True.
        4. If local time has exceeded the catch-up window (e.g. > 2 hours late), return False to avoid stale delivery.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    elif now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    user_tz = get_safe_timezone(user_tz_name)
    now_local = now_utc.astimezone(user_tz)
    today_str = now_local.strftime("%Y-%m-%d")

    # Already received today's briefing
    if last_briefing_date == today_str:
        return False, today_str

    scheduled_dt = now_local.replace(
        hour=briefing_time.hour,
        minute=briefing_time.minute,
        second=0,
        microsecond=0,
    )

    if now_local < scheduled_dt:
        # Scheduled time has not arrived yet today
        return False, today_str

    elapsed = now_local - scheduled_dt
    if elapsed <= timedelta(minutes=window_minutes):
        return True, today_str

    # Exceeded the dispatch window for today
    return False, today_str


def chunk_list(items: list[T], chunk_size: int) -> Iterator[list[T]]:
    """Yield successive chunks of items of max length chunk_size."""
    if chunk_size <= 0:
        chunk_size = 1
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


def safe_float(val: Any) -> float | None:
    """Safely convert value to float, returning None if conversion fails."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
