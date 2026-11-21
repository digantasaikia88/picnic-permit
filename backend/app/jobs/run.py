"""The hourly jobs of the portal.

    python -m app.jobs.run          run for ever, once an hour
    python -m app.jobs.run --once   run once and stop

Run as its own service (see the `worker` service in the Compose files), next
to the API. The jobs are safe to run again and again.

- Permits, and applications still open, whose travel date is over become Expired.
- Files chosen in the form but never submitted are deleted after their time.
"""

import logging
import sys
import time

from app.core.database import SessionLocal
from app.core.timeutil import today_local
from app.services import uploads, workflow

logger = logging.getLogger("app.jobs")

EVERY_SECONDS = 3600


def run_once() -> dict[str, int]:
    """Run every job once. Returns what was done, for the log and the tests."""
    with SessionLocal() as db:
        expired = workflow.expire_due(db, today=today_local())
        purged = uploads.purge_expired(db)
        db.commit()
    return {"expired": expired, "temporary_files_deleted": purged}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    once = "--once" in sys.argv[1:]
    while True:
        try:
            logger.info("Jobs done: %s", run_once())
        except Exception:
            # One bad run must not stop the next one.
            logger.exception("The jobs failed. They run again at the next turn.")
        if once:
            return 0
        time.sleep(EVERY_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
