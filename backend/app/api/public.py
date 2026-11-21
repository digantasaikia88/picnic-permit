"""Open endpoints of the public pages: dropdown lists and the application form.

No login. Every request is rate-limited by IP address, and an OTP is sent
only after a captcha.
"""

from fastapi import APIRouter, Depends, Form, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.errors import DomainError, FormError
from app.core.timeutil import today_local
from app.models import DocType, VehicleType
from app.schemas.application import (
    ApplicationIn,
    CheckResult,
    DocumentRule,
    FormConfig,
    OtpRequest,
    OtpSent,
    SeasonOut,
    SubmitRequest,
    Submitted,
    UploadOut,
    VehicleTypeOut,
)
from app.schemas.masters import PublicDistrict, PublicPoliceStation
from app.services import (
    applications,
    captcha,
    flags,
    masters,
    otp,
    rate_limit,
    uploads,
    validation,
)
from app.services import settings as app_settings

router = APIRouter(prefix="/public", tags=["public"])

_DOCUMENT_NOTES = {
    DocType.VEHICLE_PERMIT: "where required",
    DocType.SLD_CERTIFICATE: "where required",
    DocType.INSPECTION_CERTIFICATE: "if already done",
}

_FORM_DOCUMENT_ORDER = [
    DocType.RC,
    DocType.INSURANCE,
    DocType.PUC,
    DocType.VEHICLE_PERMIT,
    DocType.SLD_CERTIFICATE,
    DocType.INSPECTION_CERTIFICATE,
    DocType.OWNER_SELF_CERTIFICATE,
    DocType.DRIVING_LICENCE,
]


def client_ip(request: Request) -> str:
    """The caller's address. Behind Nginx, Uvicorn fills it from the forwarded headers."""
    return request.client.host if request.client else "unknown"


@router.get("/districts", response_model=list[PublicDistrict], summary="Active districts")
def districts(db: Session = Depends(get_db)) -> list[PublicDistrict]:
    return masters.list_districts(db, active_only=True)


@router.get(
    "/police-stations",
    response_model=list[PublicPoliceStation],
    summary="Active police stations of a district",
)
def police_stations(district_id: int, db: Session = Depends(get_db)) -> list[PublicPoliceStation]:
    return masters.list_police_stations(db, district_id=district_id, active_only=True)


@router.get("/form-config", response_model=FormConfig, summary="Rules and lists of the form")
def form_config(db: Session = Depends(get_db)) -> FormConfig:
    today = today_local()
    window = validation.travel_window(db, today)
    get = lambda key: app_settings.get_int(db, key)  # noqa: E731
    return FormConfig(
        today=today,
        min_travel_date=max(window.earliest_date, window.season_start or window.earliest_date),
        max_travel_date=min(window.latest_date, window.season_end or window.latest_date),
        season=SeasonOut(start_date=window.season_start, end_date=window.season_end),
        min_days_before_travel=get(app_settings.MIN_DAYS_BEFORE_TRAVEL),
        max_days_before_travel=get(app_settings.MAX_DAYS_BEFORE_TRAVEL),
        earliest_departure_hour=get(app_settings.EARLIEST_DEPARTURE_HOUR),
        latest_return_hour=get(app_settings.LATEST_RETURN_HOUR),
        leader_min_age=get(app_settings.LEADER_MIN_AGE),
        child_free_below_age=get(app_settings.CHILD_FREE_BELOW_AGE),
        upload_max_mb=get(app_settings.UPLOAD_MAX_MB),
        otp_length=get(app_settings.OTP_LENGTH),
        otp_resend_seconds=get(app_settings.OTP_RESEND_SECONDS),
        vehicle_types=[
            VehicleTypeOut.model_validate(row)
            for row in db.scalars(
                select(VehicleType).where(VehicleType.is_active).order_by(VehicleType.id)
            )
        ],
        documents=[
            DocumentRule(
                doc_type=doc_type,
                label=validation.DOCUMENT_LABELS[doc_type],
                required=doc_type in validation.REQUIRED_DOCUMENTS,
                note=_DOCUMENT_NOTES.get(doc_type),
            )
            for doc_type in _FORM_DOCUMENT_ORDER
        ],
    )


@router.post(
    "/uploads",
    response_model=UploadOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload one document of the form",
)
async def upload(
    request: Request,
    file: UploadFile,
    doc_type: DocType = Form(),
    db: Session = Depends(get_db),
) -> UploadOut:
    if doc_type not in validation.DOCUMENT_LABELS:
        raise DomainError("This document is not asked for in the form.")
    rate_limit.hit(db, f"upload:{client_ip(request)}", limit=rate_limit.UPLOADS_PER_IP)
    content = await file.read(uploads.max_bytes(db) + 1)
    saved = uploads.save_temp(db, filename=file.filename or "", content=content, doc_type=doc_type)
    db.commit()
    return UploadOut(
        token=saved.token,
        doc_type=saved.doc_type,
        original_name=saved.original_name,
        size_bytes=saved.size_bytes,
    )


@router.delete(
    "/uploads/{token}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove an uploaded file"
)
def delete_upload(token: str, db: Session = Depends(get_db)) -> None:
    # The token is long and random, and known only to the browser that uploaded the file.
    uploads.delete_temp(db, token)
    db.commit()


@router.post(
    "/applications/check",
    response_model=CheckResult,
    summary="Validate the form and run the duplicate check, without saving",
)
def check_application(
    body: ApplicationIn, request: Request, db: Session = Depends(get_db)
) -> CheckResult:
    rate_limit.hit(db, f"check:{client_ip(request)}", limit=rate_limit.CHECKS_PER_IP)
    db.commit()
    return applications.check(db, body)


@router.post("/applications/otp", response_model=OtpSent, summary="Send the undertaking OTP")
def send_otp(
    body: OtpRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OtpSent:
    if settings.captcha_enabled and not captcha.verify(db, body.captcha_id, body.captcha_answer):
        db.commit()
        raise DomainError("The captcha text is not correct. Please try the new one.")
    if not validation._MOBILE_RE.fullmatch(body.mobile):
        raise FormError({"leader_mobile": "Enter the group leader's 10-digit mobile number."})
    flags.refuse_if_blocked(db, body.mobile)

    rate_limit.hit(db, f"otp:{client_ip(request)}", limit=rate_limit.OTPS_PER_IP)
    challenge, code = otp.request(db, mobile=body.mobile, purpose=otp.PURPOSE_SUBMIT)
    db.commit()
    return OtpSent(
        otp_id=challenge.id,
        dev_otp=None if settings.is_production else code,
        valid_minutes=app_settings.get_int(db, app_settings.OTP_VALID_MINUTES),
        resend_after_seconds=app_settings.get_int(db, app_settings.OTP_RESEND_SECONDS),
    )


@router.post(
    "/applications",
    response_model=Submitted,
    status_code=status.HTTP_201_CREATED,
    summary="Submit the application",
)
def submit_application(
    body: SubmitRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> Submitted:
    rate_limit.hit(db, f"submit:{client_ip(request)}", limit=rate_limit.SUBMISSIONS_PER_IP)
    db.commit()
    application = applications.submit(
        db,
        body.application,
        otp_id=body.otp_id,
        otp_code=body.otp_code,
        raise_claim=body.raise_claim,
    )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    if application.is_duplicate_claim:
        message = (
            "Your application is on hold. Another application exists for the same vehicle or "
            "driver on that date, and the DTO will verify your claim. "
            "This is not permission to travel."
        )
    else:
        message = (
            "Your application is submitted and is with the DTO. "
            "Submission is not permission to travel."
        )
    return Submitted(
        application_number=application.application_number,
        status=application.status,
        message=message,
    )
