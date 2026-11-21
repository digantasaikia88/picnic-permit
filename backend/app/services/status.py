"""Status search and the applicant's OTP-confirmed session (PRD Section 3.1).

- Anyone can search by application number and sees only the number, travel
  date, current office, status and the remarks of a return or rejection.
- A search by mobile number needs an OTP sent to that number.
- The full application, its documents, correction and the inspection
  certificate upload need an OTP to the group leader's mobile. After the OTP
  the browser holds a short session tied to that mobile number.
"""

import hashlib
import secrets
import uuid
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError, NotFoundError
from app.core.timeutil import now_utc
from app.models import (
    ApplicantSession,
    Application,
    ApplicationDocument,
    DocType,
    InspectionStatus,
    Status,
    TempUpload,
)
from app.services import audit, otp, uploads, workflow
from app.services import settings as app_settings

# Statuses in which the remarks are shown to the public.
_REMARK_STATUSES = (Status.RETURNED_TO_APPLICANT, Status.REJECTED)


def find_by_number(db: Session, number: str) -> Application | None:
    digits = "".join(ch for ch in number if ch.isdigit())
    if len(digits) != 11:
        return None
    return db.scalar(select(Application).where(Application.application_number == digits))


def list_for_mobile(db: Session, mobile: str) -> list[Application]:
    return list(
        db.scalars(
            select(Application)
            .where(Application.leader_mobile == mobile)
            .order_by(Application.submitted_at.desc())
        )
    )


def current_office(application: Application) -> str:
    """Where the application is now, in words the applicant understands."""
    name = workflow.office_name(application)
    if name:
        return name
    if application.status == Status.RETURNED_TO_APPLICANT:
        return "With the applicant, for correction"
    return "Closed"


def remarks_for_public(application: Application) -> str | None:
    if application.status in _REMARK_STATUSES:
        return application.status_remarks
    return None


def mask_mobile(mobile: str) -> str:
    """Only the last two digits: enough for the leader to recognise the number."""
    return "*" * (len(mobile) - 2) + mobile[-2:]


# ------------------------------------------------------------------- OTP


def request_access_otp(
    db: Session, *, mobile: str | None, application_number: str | None
) -> tuple[str, str | None, str | None]:
    """Send an OTP for the status page. Returns (otp id, code or None, masked mobile or None).

    By mobile number: the OTP is sent only if that number has applications, but
    the answer looks the same either way, so nobody can test which numbers
    have applied.

    By application number: the OTP goes to the group leader's mobile of that
    application, shown masked.
    """
    if application_number:
        application = find_by_number(db, application_number)
        if application is None:
            raise NotFoundError("No application was found with this number.")
        challenge, code = otp.request(
            db, mobile=application.leader_mobile, purpose=otp.PURPOSE_STATUS
        )
        return challenge.id, code, mask_mobile(application.leader_mobile)

    if not mobile:
        raise DomainError("Enter an application number or a mobile number.")
    if not list_for_mobile(db, mobile):
        # A made-up id: any code entered against it is simply "not valid".
        return str(uuid.uuid4()), None, None
    challenge, code = otp.request(db, mobile=mobile, purpose=otp.PURPOSE_STATUS)
    return challenge.id, code, None


# --------------------------------------------------------------- sessions


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def open_session(db: Session, *, otp_id: str, otp_code: str) -> tuple[str, int, str]:
    """Check the OTP and start a session. Returns (cookie token, seconds, mobile)."""
    challenge = otp.verify_by_id(db, otp_id=otp_id, purpose=otp.PURPOSE_STATUS, code=otp_code)
    otp.consume(challenge)

    now = now_utc()
    db.execute(delete(ApplicantSession).where(ApplicantSession.expires_at < now))
    minutes = app_settings.get_int(db, app_settings.APPLICANT_SESSION_MINUTES)
    token = secrets.token_urlsafe(32)
    db.add(
        ApplicantSession(
            token_hash=_hash(token),
            mobile=challenge.mobile,
            created_at=now,
            expires_at=now + timedelta(minutes=minutes),
        )
    )
    return token, minutes * 60, challenge.mobile


def find_session(db: Session, token: str | None) -> ApplicantSession | None:
    if not token:
        return None
    session = db.scalar(select(ApplicantSession).where(ApplicantSession.token_hash == _hash(token)))
    if session is None or session.expires_at <= now_utc():
        return None
    return session


def close_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(ApplicantSession).where(ApplicantSession.token_hash == _hash(token)))


def own_application(db: Session, session: ApplicantSession, number: str) -> Application:
    """An application of the signed-in mobile number.

    Someone else's application answers exactly like a number that does not
    exist, so the session cannot be used to probe other applications.
    """
    application = find_by_number(db, number)
    if application is None or application.leader_mobile != session.mobile:
        raise NotFoundError("Application not found.")
    return application


def own_document(application: Application, document_id: int) -> ApplicationDocument:
    for document in application.documents:
        if document.id == document_id:
            return document
    raise NotFoundError("Document not found.")


# ------------------------------------------------- inspection certificate


def can_upload_inspection_certificate(application: Application) -> bool:
    """The applicant may upload the certificate while the application is with the DTO."""
    return application.status == Status.PENDING_DTO


def upload_inspection_certificate(
    db: Session, application: Application, upload: TempUpload
) -> None:
    if not can_upload_inspection_certificate(application):
        raise DomainError(
            "The inspection certificate can be uploaded only while the application is with the DTO."
        )
    old_names = [d.original_name for d in application.documents if d.doc_type == upload.doc_type]
    old_status = application.inspection_status
    uploads.replace(db, application, {DocType.INSPECTION_CERTIFICATE: upload})
    # A result already recorded by the DTO stays: the DTO confirms the new file itself.
    if application.inspection_status in (
        InspectionStatus.INSPECTION_REQUIRED,
        InspectionStatus.INSPECTION_SCHEDULED,
    ):
        application.inspection_status = InspectionStatus.CERTIFICATE_UPLOADED
    audit.record(
        db,
        actor=None,
        system_label=workflow.APPLICANT,
        action="application.inspection_certificate_uploaded",
        entity_type="application",
        entity_id=application.id,
        entity_label=application.application_number,
        old={"inspection_status": old_status.value, "file": old_names[0] if old_names else None},
        new={
            "inspection_status": application.inspection_status.value,
            "file": upload.original_name,
        },
    )
