"""SQLAlchemy models. Alembic reads `Base.metadata` to autogenerate migrations.

Import every model module here as it is added, so Alembic can see it.
"""

from app.models.application import (
    ApplicantSession,
    Application,
    ApplicationDocument,
    ApplicationPassenger,
    ApplicationSequence,
    DocType,
    DrivingBand,
    EmergencyContact,
    FlaggedMobile,
    Gender,
    InspectionStatus,
    OtpChallenge,
    PicnicSeason,
    RateLimitEvent,
    RemarkReason,
    SmsLog,
    Status,
    TempUpload,
    VehicleType,
    VehicleUsage,
    WorkingStatus,
)
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.masters import District, DtoOffice, PoliceStation
from app.models.setting import AppSetting
from app.models.user import Captcha, Role, User, UserSession

__all__ = [
    "AppSetting",
    "ApplicantSession",
    "EmergencyContact",
    "FlaggedMobile",
    "Application",
    "ApplicationDocument",
    "ApplicationPassenger",
    "ApplicationSequence",
    "AuditLog",
    "Base",
    "Captcha",
    "District",
    "DocType",
    "DrivingBand",
    "DtoOffice",
    "Gender",
    "InspectionStatus",
    "OtpChallenge",
    "PicnicSeason",
    "PoliceStation",
    "RateLimitEvent",
    "Role",
    "SmsLog",
    "Status",
    "RemarkReason",
    "TempUpload",
    "User",
    "UserSession",
    "VehicleType",
    "VehicleUsage",
    "WorkingStatus",
]
