"""Time helpers. Rules and displays use Indian time; timestamps are stored in UTC."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def now_utc() -> datetime:
    return datetime.now(UTC)


def today_local() -> date:
    """Today's date in the portal's time zone (Asia/Kolkata)."""
    return datetime.now(ZoneInfo(get_settings().app_timezone)).date()
