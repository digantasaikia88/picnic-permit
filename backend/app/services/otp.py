"""One-time passwords sent by SMS.

Only a hash of the code is stored. A code works once, for a few minutes, and
for a limited number of wrong attempts.
"""

import hashlib
import math
import secrets
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError, TooManyRequestsError
from app.core.timeutil import now_utc
from app.models import OtpChallenge
from app.services import settings as app_settings
from app.services import sms

PURPOSE_SUBMIT = "APPLICATION_SUBMIT"
PURPOSE_STATUS = "STATUS_ACCESS"


def _hash(challenge_id: str, code: str) -> str:
    return hashlib.sha256(f"{challenge_id}:{code.strip()}".encode()).hexdigest()


def request(db: Session, *, mobile: str, purpose: str) -> tuple[OtpChallenge, str]:
    """Create an OTP and send it by SMS. Returns (challenge, code)."""
    now = now_utc()

    latest = db.scalar(
        select(OtpChallenge)
        .where(OtpChallenge.mobile == mobile)
        .order_by(OtpChallenge.created_at.desc())
        .limit(1)
    )
    wait = app_settings.get_int(db, app_settings.OTP_RESEND_SECONDS)
    if latest is not None:
        elapsed = (now - latest.created_at).total_seconds()
        if elapsed < wait:
            raise TooManyRequestsError(
                f"An OTP was just sent. You can ask for another in {math.ceil(wait - elapsed)} "
                "second(s)."
            )

    sent_this_hour = db.scalar(
        select(func.count())
        .select_from(OtpChallenge)
        .where(OtpChallenge.mobile == mobile, OtpChallenge.created_at >= now - timedelta(hours=1))
    )
    if (sent_this_hour or 0) >= app_settings.get_int(db, app_settings.OTP_MAX_PER_HOUR):
        raise TooManyRequestsError(
            "Too many OTPs were sent to this mobile number. Please try again after 1 hour."
        )

    length = app_settings.get_int(db, app_settings.OTP_LENGTH)
    valid_minutes = app_settings.get_int(db, app_settings.OTP_VALID_MINUTES)
    code = "".join(secrets.choice("0123456789") for _ in range(length))
    challenge = OtpChallenge(
        id=str(uuid.uuid4()),
        mobile=mobile,
        purpose=purpose,
        code_hash="",
        created_at=now,
        expires_at=now + timedelta(minutes=valid_minutes),
    )
    challenge.code_hash = _hash(challenge.id, code)
    db.add(challenge)
    db.flush()

    text = (
        f"{{code}} is your OTP for the Picnic Portal. Valid for {valid_minutes} minutes. "
        "Do not share it with anyone."
    )
    sms.send(
        db,
        mobile=mobile,
        kind=sms.KIND_OTP,
        message=text.format(code=code),
        safe_message=text.format(code="[OTP]"),
    )
    return challenge, code


def verify(db: Session, *, otp_id: str, mobile: str, purpose: str, code: str) -> OtpChallenge:
    """Check a code. A wrong attempt is counted and saved before the error is raised.

    The caller marks the challenge consumed (`consume`) once its own work has succeeded.
    """
    challenge = db.get(OtpChallenge, otp_id)
    if (
        challenge is None
        or challenge.mobile != mobile
        or challenge.purpose != purpose
        or challenge.consumed_at is not None
    ):
        raise DomainError("This OTP is not valid. Please ask for a new one.")
    if challenge.expires_at <= now_utc():
        raise DomainError("This OTP has expired. Please ask for a new one.")

    max_attempts = app_settings.get_int(db, app_settings.OTP_MAX_ATTEMPTS)
    if challenge.attempts >= max_attempts:
        raise DomainError("Too many wrong attempts. Please ask for a new OTP.")

    if not secrets.compare_digest(challenge.code_hash, _hash(challenge.id, code)):
        challenge.attempts += 1
        left = max_attempts - challenge.attempts
        db.commit()
        if left <= 0:
            raise DomainError("The OTP is not correct. Please ask for a new OTP.")
        raise DomainError(f"The OTP is not correct. {left} attempt(s) left.")
    return challenge


def consume(challenge: OtpChallenge) -> None:
    challenge.consumed_at = now_utc()


def verify_by_id(db: Session, *, otp_id: str, purpose: str, code: str) -> OtpChallenge:
    """Check a code when the caller does not hold the mobile number itself.

    Used by the status page, where the OTP may have been sent to the group
    leader's number of an application that the visitor only knows by its number.
    """
    challenge = db.get(OtpChallenge, otp_id)
    if challenge is None:
        raise DomainError("This OTP is not valid. Please ask for a new one.")
    return verify(db, otp_id=otp_id, mobile=challenge.mobile, purpose=purpose, code=code)
