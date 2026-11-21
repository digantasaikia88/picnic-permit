"""Sending SMS. Everything that sends an SMS goes through `send`.

The real gateway is not decided yet. Until it is, the console gateway writes
the message to the backend log: in development that is how you read an OTP.
In production the console gateway hides secret parts, so an OTP never reaches
a log file.

To add the real gateway: write a class with the same `send` method, and return
it from `get_gateway` when the setting says so.
"""

import logging
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Application, SmsLog

logger = logging.getLogger(__name__)

KIND_OTP = "OTP"
KIND_SUBMITTED = "APPLICATION_SUBMITTED"
KIND_ON_HOLD = "APPLICATION_ON_HOLD"
KIND_RETURNED = "APPLICATION_RETURNED"
KIND_RESUBMITTED = "APPLICATION_RESUBMITTED"
KIND_FORWARDED = "APPLICATION_FORWARDED"
KIND_APPROVED = "APPLICATION_APPROVED"
KIND_REJECTED = "APPLICATION_REJECTED"
KIND_CORRECTED = "APPLICATION_CORRECTED"
KIND_EXPIRED = "APPLICATION_EXPIRED"
KIND_TRANSFERRED = "APPLICATION_TRANSFERRED"
KIND_CLAIM_ACCEPTED = "DUPLICATE_CLAIM_ACCEPTED"
KIND_INSPECTION_SCHEDULED = "INSPECTION_SCHEDULED"
KIND_INSPECTION_RESULT = "INSPECTION_RESULT"


class SmsGateway(Protocol):
    def send(self, mobile: str, message: str, *, safe_message: str) -> None: ...


class ConsoleGateway:
    """Writes the SMS to the log instead of sending it."""

    def send(self, mobile: str, message: str, *, safe_message: str) -> None:
        shown = safe_message if get_settings().is_production else message
        logger.warning("SMS to %s: %s", mobile, shown)


_gateway: SmsGateway = ConsoleGateway()


def get_gateway() -> SmsGateway:
    return _gateway


def send(
    db: Session,
    *,
    mobile: str,
    message: str,
    kind: str,
    application: Application | None = None,
    safe_message: str | None = None,
) -> None:
    """Send one SMS and record it.

    `safe_message` is the text with secrets (an OTP) left out. It is what gets
    stored in the SMS log, so that codes are never kept in the database.
    """
    stored = safe_message or message
    db.add(
        SmsLog(
            mobile=mobile,
            kind=kind,
            message=stored,
            application_id=application.id if application else None,
        )
    )
    get_gateway().send(mobile, message, safe_message=stored)
