"""Public status search, and the group leader's OTP-confirmed access to an application."""

from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.public import client_ip
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.errors import AuthenticationError, DomainError, FormError, NotFoundError
from app.core.timeutil import now_utc
from app.models import ApplicantSession, Application, District, DocType, EmergencyContact
from app.models import Status as ApplicationStatus
from app.schemas.application import (
    ApplicantMe,
    ApplicationDetail,
    ApplicationIn,
    DocumentOut,
    EmergencyContactOut,
    PassengerOut,
    PublicStatus,
    StatusOtpRequest,
    StatusOtpSent,
    StatusSessionRequest,
)
from app.services import (
    applications,
    captcha,
    officer,
    rate_limit,
    uploads,
    validation,
    workflow,
)
from app.services import settings as app_settings
from app.services import status as status_service

router = APIRouter(prefix="/public", tags=["public: status"])

APPLICANT_COOKIE = "pp_applicant"
EXISTING = "existing:"


def _public(application: Application) -> PublicStatus:
    return PublicStatus(
        application_number=application.application_number,
        travel_date=application.travel_date,
        status=application.status,
        status_label=workflow.STATUS_LABELS[application.status],
        current_office=status_service.current_office(application),
        remarks=status_service.remarks_for_public(application),
        working_status=officer.working_status_label(application),
    )


def form_values(application: Application) -> dict[str, object]:
    """The application in the shape of the form, so a correction starts from it."""
    a = application
    return {
        "leader_name": a.leader_name,
        "leader_age": str(a.leader_age),
        "leader_gender": a.leader_gender.value,
        "leader_mobile": a.leader_mobile,
        "travel_date": a.travel_date.isoformat(),
        "departure_time": a.departure_time.strftime("%H:%M"),
        "return_time": a.return_time.strftime("%H:%M"),
        "origin_address": a.origin_address,
        "origin_district_id": str(a.origin_district_id),
        "origin_police_station_id": str(a.origin_police_station_id),
        "destination_address": a.destination_address,
        "destination_district_id": str(a.destination_district_id),
        "destination_police_station_id": str(a.destination_police_station_id or ""),
        "driving_band": a.driving_band.value,
        "vehicle_reg_number": a.vehicle_reg_number,
        "vehicle_type_id": str(a.vehicle_type_id),
        "vehicle_usage": a.vehicle_usage.value,
        "seating_capacity": str(a.seating_capacity),
        "owner_name": a.owner_name,
        "owner_mobile": a.owner_mobile,
        "driver_name": a.driver_name,
        "licence_number": a.licence_number,
        "licence_class": a.licence_class,
        "licence_valid_until": a.licence_valid_until.isoformat(),
        "driver_mobile": a.driver_mobile,
        "has_handyman": a.has_handyman,
        "handyman_name": a.handyman_name or "",
        "handyman_mobile": a.handyman_mobile or "",
        "members": [
            {"name": p.name, "age": str(p.age), "gender": p.gender.value}
            for p in a.passengers
            if not p.is_group_leader
        ],
        **{tick: bool(value) for tick, value in a.declarations.items()},
        "documents": {
            d.doc_type.value: {
                "token": f"{EXISTING}{d.id}",
                "name": d.original_name,
                "size": d.size_bytes,
            }
            for d in a.documents
            if d.doc_type in validation.DOCUMENT_LABELS
        },
    }


def _detail(application: Application) -> ApplicationDetail:
    a = application
    return ApplicationDetail(
        **_public(a).model_dump(),
        submitted_on=a.submission_date,
        inspection_status=a.inspection_status.value,
        can_correct=a.status == ApplicationStatus.RETURNED_TO_APPLICANT,
        can_upload_inspection_certificate=status_service.can_upload_inspection_certificate(a),
        can_download_permit=(a.status == ApplicationStatus.APPROVED and a.verify_code is not None),
        form=form_values(a),
        origin_district=a.origin_district.name,
        origin_police_station=a.origin_police_station.name,
        destination_district=a.destination_district.name,
        destination_police_station=(
            a.destination_police_station.name if a.destination_police_station else None
        ),
        vehicle_type=a.vehicle_type.name,
        total_people=a.total_people,
        passengers=[PassengerOut.model_validate(p) for p in a.passengers],
        documents=[
            DocumentOut(
                id=d.id,
                doc_type=d.doc_type,
                label=validation.DOCUMENT_LABELS.get(d.doc_type, "Road tax payment proof"),
                original_name=d.original_name,
                size_bytes=d.size_bytes,
            )
            for d in sorted(a.documents, key=lambda d: d.id)
        ],
    )


# ------------------------------------------------------------ open search


@router.get(
    "/status/{application_number}",
    response_model=PublicStatus,
    summary="Status of an application, by its number. Open to anyone",
)
def status_by_number(
    application_number: str, request: Request, db: Session = Depends(get_db)
) -> PublicStatus:
    rate_limit.hit(db, f"status:{client_ip(request)}", limit=rate_limit.STATUS_SEARCHES_PER_IP)
    db.commit()
    application = status_service.find_by_number(db, application_number)
    if application is None:
        raise NotFoundError("No application was found with this number.")
    return _public(application)


# ------------------------------------------------------------- OTP access


@router.post("/status-access/otp", response_model=StatusOtpSent, summary="Send the status OTP")
def send_status_otp(
    body: StatusOtpRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StatusOtpSent:
    if settings.captcha_enabled and not captcha.verify(db, body.captcha_id, body.captcha_answer):
        db.commit()
        raise DomainError("The captcha text is not correct. Please try the new one.")
    if not body.application_number and not validation._MOBILE_RE.fullmatch(body.mobile or ""):
        raise FormError({"mobile": "Enter a 10-digit mobile number."})

    rate_limit.hit(db, f"otp:{client_ip(request)}", limit=rate_limit.OTPS_PER_IP)
    otp_id, code, sent_to = status_service.request_access_otp(
        db, mobile=body.mobile, application_number=body.application_number
    )
    db.commit()
    return StatusOtpSent(
        otp_id=otp_id,
        valid_minutes=app_settings.get_int(db, app_settings.OTP_VALID_MINUTES),
        resend_after_seconds=app_settings.get_int(db, app_settings.OTP_RESEND_SECONDS),
        sent_to=sent_to,
        dev_otp=None if settings.is_production else code,
    )


@router.post("/status-access/session", response_model=ApplicantMe, summary="Confirm the OTP")
def open_session(
    body: StatusSessionRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ApplicantMe:
    token, seconds, mobile = status_service.open_session(
        db, otp_id=body.otp_id, otp_code=body.otp_code
    )
    db.commit()
    response.set_cookie(
        APPLICANT_COOKIE,
        token,
        max_age=seconds,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )
    return ApplicantMe(mobile=mobile, expires_in_seconds=seconds)


@dataclass(frozen=True)
class Applicant:
    session: ApplicantSession
    token: str


def current_applicant(request: Request, db: Session = Depends(get_db)) -> Applicant:
    token = request.cookies.get(APPLICANT_COOKIE)
    session = status_service.find_session(db, token)
    if session is None or token is None:
        raise AuthenticationError("Please confirm the OTP to continue.")
    return Applicant(session=session, token=token)


@router.post(
    "/status-access/logout", status_code=status.HTTP_204_NO_CONTENT, summary="End the session"
)
def close_session(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    status_service.close_session(db, request.cookies.get(APPLICANT_COOKIE))
    db.commit()
    response.delete_cookie(APPLICANT_COOKIE, path="/")


# ------------------------------------- the signed-in group leader's own data


@router.get("/my/session", response_model=ApplicantMe, summary="The confirmed mobile number")
def my_session(applicant: Applicant = Depends(current_applicant)) -> ApplicantMe:
    left = int((applicant.session.expires_at - now_utc()).total_seconds())
    return ApplicantMe(mobile=applicant.session.mobile, expires_in_seconds=max(left, 0))


@router.get(
    "/my/applications",
    response_model=list[PublicStatus],
    summary="Every application of the confirmed mobile number",
)
def my_applications(
    applicant: Applicant = Depends(current_applicant), db: Session = Depends(get_db)
) -> list[PublicStatus]:
    return [_public(a) for a in status_service.list_for_mobile(db, applicant.session.mobile)]


@router.get(
    "/my/applications/{application_number}",
    response_model=ApplicationDetail,
    summary="The full application",
)
def my_application(
    application_number: str,
    response: Response,
    applicant: Applicant = Depends(current_applicant),
    db: Session = Depends(get_db),
) -> ApplicationDetail:
    response.headers["Cache-Control"] = "no-store"
    return _detail(status_service.own_application(db, applicant.session, application_number))


@router.get(
    "/my/applications/{application_number}/documents/{document_id}",
    summary="Download one document of the application",
)
def my_document(
    application_number: str,
    document_id: int,
    applicant: Applicant = Depends(current_applicant),
    db: Session = Depends(get_db),
) -> FileResponse:
    application = status_service.own_application(db, applicant.session, application_number)
    document = status_service.own_document(application, document_id)
    path = uploads.document_path(document)
    if not path.is_file():
        raise NotFoundError("The file is missing.")
    extension = path.suffix
    return FileResponse(
        path,
        media_type=document.content_type,
        filename=f"{application.application_number}_{document.doc_type.value}{extension}",
        content_disposition_type="inline",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post(
    "/my/applications/{application_number}/inspection-certificate",
    response_model=ApplicationDetail,
    summary="Upload the inspection certificate, while the application is with the DTO",
)
async def upload_inspection_certificate(
    application_number: str,
    file: UploadFile,
    request: Request,
    applicant: Applicant = Depends(current_applicant),
    db: Session = Depends(get_db),
) -> ApplicationDetail:
    application = status_service.own_application(db, applicant.session, application_number)
    if not status_service.can_upload_inspection_certificate(application):
        raise DomainError(
            "The inspection certificate can be uploaded only while the application is with the DTO."
        )
    rate_limit.hit(db, f"upload:{client_ip(request)}", limit=rate_limit.UPLOADS_PER_IP)
    content = await file.read(uploads.max_bytes(db) + 1)
    upload = uploads.save_temp(
        db,
        filename=file.filename or "",
        content=content,
        doc_type=DocType.INSPECTION_CERTIFICATE,
    )
    status_service.upload_inspection_certificate(db, application, upload)
    db.commit()
    db.refresh(application)
    return _detail(application)


@router.put(
    "/my/applications/{application_number}",
    response_model=PublicStatus,
    summary="Correct a returned application and resubmit it",
)
def correct_application(
    application_number: str,
    body: ApplicationIn,
    applicant: Applicant = Depends(current_applicant),
    db: Session = Depends(get_db),
) -> PublicStatus:
    application = status_service.own_application(db, applicant.session, application_number)
    # Documents already on the application are sent back as "existing:<id>"; only new files count.
    body.documents = {
        doc_type: token
        for doc_type, token in body.documents.items()
        if not token.startswith(EXISTING)
    }
    applications.correct(db, application, body)
    db.commit()
    db.refresh(application)
    return _public(application)


# ------------------------------------------------------ emergency contacts


@router.get(
    "/emergency-contacts",
    response_model=list[EmergencyContactOut],
    summary="Emergency numbers of a district",
)
def emergency_contacts(
    district_id: int, db: Session = Depends(get_db)
) -> list[EmergencyContactOut]:
    return list(
        db.scalars(
            select(EmergencyContact)
            .join(District)
            .where(
                EmergencyContact.district_id == district_id,
                EmergencyContact.is_active,
                District.is_active,
            )
            .order_by(EmergencyContact.id)
        )
    )
