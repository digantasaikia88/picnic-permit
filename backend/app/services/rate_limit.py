"""Simple request limits for the public pages, counted in the database."""

from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import TooManyRequestsError
from app.core.timeutil import now_utc
from app.models import RateLimitEvent

_HOUR = 3600

# Per IP address, per hour. Generous for a facilitation centre that files for
# many groups from one connection, and low enough to stop a script.
UPLOADS_PER_IP = 300
CHECKS_PER_IP = 120
OTPS_PER_IP = 60
SUBMISSIONS_PER_IP = 60
STATUS_SEARCHES_PER_IP = 60


def hit(db: Session, bucket: str, *, limit: int, window_seconds: int = _HOUR) -> None:
    """Count one request in `bucket`, or refuse it if the limit is reached."""
    now = now_utc()
    since = now - timedelta(seconds=window_seconds)
    # Old rows of any bucket are no longer needed.
    db.execute(delete(RateLimitEvent).where(RateLimitEvent.at < now - timedelta(days=1)))

    used = db.scalar(
        select(func.count())
        .select_from(RateLimitEvent)
        .where(RateLimitEvent.bucket == bucket, RateLimitEvent.at >= since)
    )
    if (used or 0) >= limit:
        raise TooManyRequestsError("Too many requests. Please try again after some time.")
    db.add(RateLimitEvent(bucket=bucket, at=now))
    db.flush()
