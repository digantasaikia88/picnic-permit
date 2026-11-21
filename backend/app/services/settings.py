"""Whole-number settings kept in the database (PRD Section 13.4).

The rows are created by the migration. The defaults here are used only if a
row is missing, so a rule never fails for want of a setting.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError, NotFoundError
from app.models import AppSetting, User
from app.services import audit


@dataclass(frozen=True)
class SettingSpec:
    key: str
    default: int
    min_value: int
    max_value: int
    description: str


LOGIN_MAX_FAILED_ATTEMPTS = "login_max_failed_attempts"
LOGIN_LOCK_MINUTES = "login_lock_minutes"
PASSWORD_MIN_LENGTH = "password_min_length"
GENERATED_PASSWORD_LENGTH = "generated_password_length"
SESSION_HOURS = "session_hours"
CAPTCHA_VALID_MINUTES = "captcha_valid_minutes"
MIN_DAYS_BEFORE_TRAVEL = "min_days_before_travel"
MAX_DAYS_BEFORE_TRAVEL = "max_days_before_travel"
EARLIEST_DEPARTURE_HOUR = "earliest_departure_hour"
LATEST_RETURN_HOUR = "latest_return_hour"
LEADER_MIN_AGE = "leader_min_age"
CHILD_FREE_BELOW_AGE = "child_free_below_age"
UPLOAD_MAX_MB = "upload_max_mb"
TEMP_UPLOAD_HOURS = "temp_upload_hours"
OTP_LENGTH = "otp_length"
OTP_VALID_MINUTES = "otp_valid_minutes"
OTP_MAX_ATTEMPTS = "otp_max_attempts"
OTP_RESEND_SECONDS = "otp_resend_seconds"
OTP_MAX_PER_HOUR = "otp_max_per_hour"
APPLICATIONS_PER_MOBILE_PER_DAY = "applications_per_mobile_per_day"
APPLICANT_SESSION_MINUTES = "applicant_session_minutes"

SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        LOGIN_MAX_FAILED_ATTEMPTS,
        5,
        3,
        20,
        "Wrong passwords in a row before an officer account is locked",
    ),
    SettingSpec(LOGIN_LOCK_MINUTES, 15, 1, 1440, "Minutes an officer account stays locked"),
    SettingSpec(PASSWORD_MIN_LENGTH, 8, 8, 64, "Minimum number of characters in a password"),
    SettingSpec(
        GENERATED_PASSWORD_LENGTH, 10, 8, 32, "Number of characters in an auto-generated password"
    ),
    SettingSpec(
        SESSION_HOURS, 48, 1, 720, "Hours an officer stays logged in, with or without activity"
    ),
    SettingSpec(CAPTCHA_VALID_MINUTES, 5, 1, 30, "Minutes a login captcha stays valid"),
    SettingSpec(
        MIN_DAYS_BEFORE_TRAVEL, 7, 0, 60, "Earliest travel date: days after the date of submission"
    ),
    SettingSpec(
        MAX_DAYS_BEFORE_TRAVEL, 90, 7, 365, "Latest travel date: days after the date of submission"
    ),
    SettingSpec(
        EARLIEST_DEPARTURE_HOUR, 7, 0, 22, "Earliest departure, hour of the day (7 means 7:00 AM)"
    ),
    SettingSpec(LATEST_RETURN_HOUR, 18, 1, 23, "Latest return, hour of the day (18 means 6:00 PM)"),
    SettingSpec(LEADER_MIN_AGE, 18, 0, 100, "Minimum age of the group leader, in years"),
    SettingSpec(
        CHILD_FREE_BELOW_AGE,
        0,
        0,
        18,
        "Children younger than this age do not count towards the seats (0 means everyone counts)",
    ),
    SettingSpec(UPLOAD_MAX_MB, 5, 1, 20, "Largest size of an uploaded file, in MB"),
    SettingSpec(
        TEMP_UPLOAD_HOURS, 24, 1, 168, "Hours an uploaded file is kept if the form is not submitted"
    ),
    SettingSpec(OTP_LENGTH, 6, 4, 8, "Number of digits in an OTP"),
    SettingSpec(OTP_VALID_MINUTES, 5, 1, 30, "Minutes an OTP stays valid"),
    SettingSpec(OTP_MAX_ATTEMPTS, 3, 1, 10, "Wrong attempts allowed on one OTP"),
    SettingSpec(OTP_RESEND_SECONDS, 60, 10, 600, "Seconds to wait before another OTP can be sent"),
    SettingSpec(OTP_MAX_PER_HOUR, 5, 1, 30, "OTPs that can be sent to one mobile number in 1 hour"),
    SettingSpec(
        APPLICATIONS_PER_MOBILE_PER_DAY,
        3,
        1,
        50,
        "Applications one mobile number can submit in a day",
    ),
    SettingSpec(
        APPLICANT_SESSION_MINUTES,
        30,
        5,
        240,
        "Minutes an applicant stays signed in on the status page after the OTP",
    ),
)

_DEFAULTS = {spec.key: spec.default for spec in SPECS}


def get_int(db: Session, key: str) -> int:
    row = db.get(AppSetting, key)
    return row.value if row else _DEFAULTS[key]


def list_settings(db: Session) -> list[AppSetting]:
    return list(db.scalars(select(AppSetting).order_by(AppSetting.key)))


def update_setting(db: Session, actor: User, key: str, value: int) -> AppSetting:
    row = db.get(AppSetting, key)
    if row is None:
        raise NotFoundError("Setting not found.")
    if not row.min_value <= value <= row.max_value:
        raise DomainError(f"The value must be between {row.min_value} and {row.max_value}.")
    if value != row.value:
        audit.record(
            db,
            actor=actor,
            action="setting.update",
            entity_type="setting",
            entity_id=key,
            entity_label=key,
            old={"value": row.value},
            new={"value": value},
        )
        row.value = value
    return row
