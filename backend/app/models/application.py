"""The picnic journey application and everything submitted with it."""

from datetime import date, datetime, time
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.masters import District, DtoOffice, PoliceStation


class Status(StrEnum):
    PENDING_DTO = "PENDING_DTO"
    ON_HOLD_DUPLICATE_CLAIM = "ON_HOLD_DUPLICATE_CLAIM"
    PENDING_POLICE = "PENDING_POLICE"
    PENDING_DC = "PENDING_DC"
    RETURNED_TO_APPLICANT = "RETURNED_TO_APPLICANT"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class VehicleUsage(StrEnum):
    PRIVATE = "PRIVATE"
    HIRED = "HIRED"


class DrivingBand(StrEnum):
    UP_TO_60 = "UP_TO_60"
    FROM_60_TO_90 = "FROM_60_TO_90"


class DocType(StrEnum):
    RC = "RC"
    INSURANCE = "INSURANCE"
    PUC = "PUC"
    # No longer asked for in the form. Kept so that documents of older applications still read.
    ROAD_TAX = "ROAD_TAX"
    VEHICLE_PERMIT = "VEHICLE_PERMIT"
    SLD_CERTIFICATE = "SLD_CERTIFICATE"
    INSPECTION_CERTIFICATE = "INSPECTION_CERTIFICATE"
    OWNER_SELF_CERTIFICATE = "OWNER_SELF_CERTIFICATE"
    DRIVING_LICENCE = "DRIVING_LICENCE"


class InspectionStatus(StrEnum):
    CERTIFICATE_UPLOADED = "CERTIFICATE_UPLOADED"
    INSPECTION_REQUIRED = "INSPECTION_REQUIRED"
    INSPECTION_SCHEDULED = "INSPECTION_SCHEDULED"
    PASSED = "PASSED"
    FAILED = "FAILED"


def _enum(enum_class: type[StrEnum], name: str) -> Enum:
    return Enum(enum_class, native_enum=False, length=30, create_constraint=True, name=name)


class VehicleType(Base, TimestampMixin):
    """Vehicle types offered in Step 3. Goods vehicles are never listed here."""

    __tablename__ = "vehicle_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))


class Application(Base, TimestampMixin):
    __tablename__ = "applications"
    __table_args__ = (
        # The duplicate check looks up a vehicle or a driver on a travel date.
        Index("ix_applications_vehicle_date", "vehicle_reg_key", "travel_date"),
        Index("ix_applications_licence_date", "licence_key", "travel_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    application_number: Mapped[str] = mapped_column(String(11), unique=True)
    # Changed only by app.services.workflow.
    status: Mapped[Status] = mapped_column(_enum(Status, "status"), index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # The date of first submission in Indian time. The 7-day rule always counts from it.
    submission_date: Mapped[date] = mapped_column(Date)

    # Step 1: group leader and journey
    leader_name: Mapped[str] = mapped_column(String(100))
    leader_age: Mapped[int] = mapped_column(Integer)
    leader_gender: Mapped[Gender] = mapped_column(_enum(Gender, "leader_gender"))
    leader_mobile: Mapped[str] = mapped_column(String(10), index=True)
    travel_date: Mapped[date] = mapped_column(Date, index=True)
    departure_time: Mapped[time] = mapped_column(Time)
    return_time: Mapped[time] = mapped_column(Time)
    origin_address: Mapped[str] = mapped_column(Text)
    origin_district_id: Mapped[int] = mapped_column(
        ForeignKey("districts.id", ondelete="RESTRICT"), index=True
    )
    origin_police_station_id: Mapped[int] = mapped_column(
        ForeignKey("police_stations.id", ondelete="RESTRICT"), index=True
    )
    # Routing: the DTO office of the origin district at the time of submission.
    dto_office_id: Mapped[int] = mapped_column(
        ForeignKey("dto_offices.id", ondelete="RESTRICT"), index=True
    )

    # Step 2: destination
    destination_address: Mapped[str] = mapped_column(Text)
    destination_district_id: Mapped[int] = mapped_column(
        ForeignKey("districts.id", ondelete="RESTRICT"), index=True
    )
    destination_police_station_id: Mapped[int | None] = mapped_column(
        ForeignKey("police_stations.id", ondelete="RESTRICT"), index=True
    )
    driving_band: Mapped[DrivingBand] = mapped_column(_enum(DrivingBand, "driving_band"))
    needs_dc_specific_approval: Mapped[bool] = mapped_column(server_default=text("false"))

    # Step 3: vehicle. The number is stored without spaces, in capitals.
    # The key also drops hyphens and is what the duplicate check compares.
    vehicle_reg_number: Mapped[str] = mapped_column(String(20))
    vehicle_reg_key: Mapped[str] = mapped_column(String(20))
    vehicle_type_id: Mapped[int] = mapped_column(
        ForeignKey("vehicle_types.id", ondelete="RESTRICT")
    )
    vehicle_usage: Mapped[VehicleUsage] = mapped_column(_enum(VehicleUsage, "vehicle_usage"))
    seating_capacity: Mapped[int] = mapped_column(Integer)
    owner_name: Mapped[str] = mapped_column(String(100))
    owner_mobile: Mapped[str] = mapped_column(String(10))
    inspection_status: Mapped[InspectionStatus] = mapped_column(
        _enum(InspectionStatus, "inspection_status")
    )

    # Step 4: driver and handyman
    driver_name: Mapped[str] = mapped_column(String(100))
    licence_number: Mapped[str] = mapped_column(String(25))
    licence_key: Mapped[str] = mapped_column(String(25))
    licence_class: Mapped[str] = mapped_column(String(60))
    licence_valid_until: Mapped[date] = mapped_column(Date)
    driver_mobile: Mapped[str] = mapped_column(String(10))
    has_handyman: Mapped[bool] = mapped_column(server_default=text("false"))
    handyman_name: Mapped[str | None] = mapped_column(String(100))
    handyman_mobile: Mapped[str | None] = mapped_column(String(10))

    # Steps 3, 4 and 6: the ticks, exactly as accepted by the group leader.
    declarations: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # Group leader + members + driver + handyman, as counted against the seats.
    total_people: Mapped[int] = mapped_column(Integer)

    # Section 10.1: submitted by an applicant who was blocked by the duplicate check.
    is_duplicate_claim: Mapped[bool] = mapped_column(server_default=text("false"))

    # Set when an office returns the application: where it was, so that the
    # resubmitted application goes back to the same office.
    returned_from_status: Mapped[Status | None] = mapped_column(
        _enum(Status, "returned_from_status")
    )
    # The remarks of the latest return, or the reason of a rejection. Shown to the applicant.
    status_remarks: Mapped[str | None] = mapped_column(Text)
    # Set by the office that holds the application. Empty means "Received".
    working_status_id: Mapped[int | None] = mapped_column(
        ForeignKey("working_statuses.id", ondelete="RESTRICT")
    )

    # Section 7.1: what the DTO found in VAHAN, in the challan records and in SARATHI.
    dto_findings: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Section 7.1: the inspection appointment, the checklist and the result.
    inspection: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # The inspection certificate the DTO has confirmed: one of this application,
    # or one already on record for the same vehicle. A replaced file is a new
    # document, so it has to be confirmed again.
    certificate_confirmed_doc_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "application_documents.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_applications_confirmed_certificate",
        )
    )
    # Section 7.2: the police station's verification remarks, checkpoints and comments.
    police_findings: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Section 7.3: mandatory when the DC approves a 60 to 90 minute journey.
    dc_specific_approval_remark: Mapped[str | None] = mapped_column(Text)

    # Section 8: the permit. Set once, when the DC office approves. The permit
    # number is the application number.
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # "Name, designation" of the officer who approved, as printed on the permit.
    approved_by: Mapped[str | None] = mapped_column(String(220))
    # The random part of the short verification link in the QR code.
    verify_code: Mapped[str | None] = mapped_column(String(16), unique=True)

    origin_district: Mapped[District] = relationship(foreign_keys=[origin_district_id])
    origin_police_station: Mapped[PoliceStation] = relationship(
        foreign_keys=[origin_police_station_id]
    )
    dto_office: Mapped[DtoOffice] = relationship()
    destination_district: Mapped[District] = relationship(foreign_keys=[destination_district_id])
    destination_police_station: Mapped[PoliceStation | None] = relationship(
        foreign_keys=[destination_police_station_id]
    )
    vehicle_type: Mapped[VehicleType] = relationship()
    working_status: Mapped[WorkingStatus | None] = relationship()
    passengers: Mapped[list[ApplicationPassenger]] = relationship(
        back_populates="application",
        order_by="ApplicationPassenger.position",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list[ApplicationDocument]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        foreign_keys="ApplicationDocument.application_id",
    )


class ApplicationPassenger(Base):
    """Everyone in the group. Position 1 is always the group leader."""

    __tablename__ = "application_passengers"
    __table_args__ = (UniqueConstraint("application_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[Gender] = mapped_column(_enum(Gender, "gender"))
    is_group_leader: Mapped[bool] = mapped_column(server_default=text("false"))

    application: Mapped[Application] = relationship(back_populates="passengers")


class ApplicationDocument(Base):
    """An uploaded file of an application, stored on the uploads volume under a random name."""

    __tablename__ = "application_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    doc_type: Mapped[DocType] = mapped_column(_enum(DocType, "doc_type"))
    stored_name: Mapped[str] = mapped_column(String(80), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(50))
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Checked by the DTO against the original: verified, not verified, or not yet checked.
    verified: Mapped[bool | None] = mapped_column()

    application: Mapped[Application] = relationship(
        back_populates="documents", foreign_keys=[application_id]
    )


class TempUpload(Base):
    """A file chosen in the form but not yet part of a submitted application.

    Deleted when the application is submitted (it becomes a document) or when
    it expires, whichever comes first.
    """

    __tablename__ = "temp_uploads"

    token: Mapped[str] = mapped_column(String(36), primary_key=True)
    doc_type: Mapped[DocType] = mapped_column(_enum(DocType, "doc_type"))
    stored_name: Mapped[str] = mapped_column(String(80), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(50))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ApplicationSequence(Base):
    """Last serial used for application numbers, per year and district."""

    __tablename__ = "application_sequences"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_code: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_serial: Mapped[int] = mapped_column(Integer)


class OtpChallenge(Base):
    """An OTP sent to a mobile number. Only a hash of the code is stored."""

    __tablename__ = "otp_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mobile: Mapped[str] = mapped_column(String(10), index=True)
    purpose: Mapped[str] = mapped_column(String(40))
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SmsLog(Base):
    """Every SMS the portal sent or tried to send. OTP codes are never stored here."""

    __tablename__ = "sms_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    mobile: Mapped[str] = mapped_column(String(10), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RateLimitEvent(Base):
    """One counted request, for the limits on public pages."""

    __tablename__ = "rate_limit_events"
    __table_args__ = (Index("ix_rate_limit_events_bucket_at", "bucket", "at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bucket: Mapped[str] = mapped_column(String(120))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PicnicSeason(Base, TimestampMixin):
    """The picnic season set by the State Admin. A single row, id 1.

    When both dates are set, the travel date must fall inside them.
    """

    __tablename__ = "picnic_season"

    id: Mapped[int] = mapped_column(primary_key=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)


class ApplicantSession(Base):
    """A short session of a group leader whose mobile number was confirmed by OTP.

    It lets that mobile number see its own applications in full, correct a
    returned one and upload the inspection certificate. Only a hash of the
    cookie token is stored.
    """

    __tablename__ = "applicant_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    mobile: Mapped[str] = mapped_column(String(10), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EmergencyContact(Base, TimestampMixin):
    """A district emergency number shown on the public pages."""

    __tablename__ = "emergency_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    district_id: Mapped[int] = mapped_column(
        ForeignKey("districts.id", ondelete="RESTRICT"), index=True
    )
    # What the number is, for example "District Police Control Room".
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))

    district: Mapped[District] = relationship()


class WorkingStatus(Base, TimestampMixin):
    """What an office is doing with an application it holds, shown to the applicant."""

    __tablename__ = "working_statuses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    # The offices it is offered to. Each office sees only its own list.
    for_dto: Mapped[bool] = mapped_column(server_default=text("true"))
    for_police: Mapped[bool] = mapped_column(server_default=text("true"))
    for_dc: Mapped[bool] = mapped_column(server_default=text("true"))


class RemarkReason(Base, TimestampMixin):
    """A ready reason for returning or rejecting an application, so that reports stay uniform."""

    __tablename__ = "remark_reasons"
    __table_args__ = (UniqueConstraint("kind", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # RETURN or REJECT
    kind: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(160))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))


class FlaggedMobile(Base, TimestampMixin):
    """A mobile number that filed a fake or prank application (PRD Section 10.1).

    Its later applications show a warning to officers. A State Admin can block
    it from applying.
    """

    __tablename__ = "flagged_mobiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    mobile: Mapped[str] = mapped_column(String(10), unique=True)
    reason: Mapped[str] = mapped_column(Text)
    # The application that led to the flag, and the office that flagged it.
    application_number: Mapped[str | None] = mapped_column(String(11))
    flagged_by: Mapped[str] = mapped_column(String(160))
    is_blocked: Mapped[bool] = mapped_column(server_default=text("false"))
