"""The permit: public verification, and the group leader's downloads (PRD Section 8)."""

from datetime import date, time

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.public import client_ip
from app.api.status import Applicant, current_applicant
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.core.timeutil import today_local
from app.models import Application
from app.services import duplicates, permit, rate_limit
from app.services import status as status_service

router = APIRouter(prefix="/public", tags=["public: permit"])


class PermitOut(BaseModel):
    """What the verification page shows of a permit."""

    permit_number: str
    # VALID, CANCELLED or EXPIRED
    state: str
    state_label: str
    travel_date: date
    departure_time: time
    return_time: time
    vehicle_reg_number: str
    driver_name: str
    licence_number: str
    total_people: int
    origin: str
    destination: str
    leader_mobile: str
    # True when found by the search box: the mobile and licence numbers are then hidden in part.
    masked: bool


def _mask(value: str, keep: int) -> str:
    """Hide all but the last characters, so that a number can be matched but not copied."""
    return "X" * max(len(value) - keep, 0) + value[-keep:]


def _out(application: Application, *, masked: bool) -> PermitOut:
    a = application
    state = permit.state(a, today=today_local())
    return PermitOut(
        permit_number=a.application_number,
        state=state.value,
        state_label=permit.STATE_LABELS[state],
        travel_date=a.travel_date,
        departure_time=a.departure_time,
        return_time=a.return_time,
        vehicle_reg_number=a.vehicle_reg_number,
        driver_name=a.driver_name,
        licence_number=_mask(a.licence_number, 4) if masked else a.licence_number,
        total_people=a.total_people,
        origin=f"{a.origin_police_station.name}, {a.origin_district.name}",
        destination=f"{a.destination_address}, {a.destination_district.name}",
        leader_mobile=_mask(a.leader_mobile, 2) if masked else a.leader_mobile,
        masked=masked,
    )


def _pdf(content: bytes, filename: str) -> Response:
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


# ------------------------------------------------------------ verification


@router.get(
    "/permits/search",
    response_model=list[PermitOut],
    summary="Find a permit by its number or by the vehicle number, when the QR cannot be read",
)
def search_permits(
    request: Request,
    q: str = Query(min_length=4, max_length=30),
    db: Session = Depends(get_db),
) -> list[PermitOut]:
    """Open to anyone, so the personal numbers are hidden in part.

    The full details are behind the link printed in the QR code, which cannot
    be guessed from the permit or vehicle number.
    """
    rate_limit.hit(db, f"verify:{client_ip(request)}", limit=rate_limit.STATUS_SEARCHES_PER_IP)
    db.commit()
    key = duplicates.comparison_key(q)
    digits = "".join(ch for ch in q if ch.isdigit())
    conditions = [Application.vehicle_reg_key == key]
    if digits:
        conditions.append(Application.application_number == digits)
    found = db.scalars(
        select(Application)
        .where(Application.verify_code.is_not(None), or_(*conditions))
        .order_by(Application.travel_date.desc(), Application.id.desc())
        .limit(5)
    )
    today = today_local()
    return [_out(a, masked=True) for a in found if permit.state(a, today=today) is not None]


@router.get(
    "/permits/{code}",
    response_model=PermitOut,
    summary="The live status of a permit, from the link in its QR code",
)
def verify_permit(code: str, request: Request, db: Session = Depends(get_db)) -> PermitOut:
    rate_limit.hit(db, f"verify:{client_ip(request)}", limit=rate_limit.STATUS_SEARCHES_PER_IP)
    db.commit()
    application = db.scalar(select(Application).where(Application.verify_code == code[:16]))
    if application is None or permit.state(application, today=today_local()) is None:
        raise NotFoundError("No permit was found for this code.")
    return _out(application, masked=False)


# -------------------------------------------------- the group leader's copy


@router.get(
    "/my/applications/{application_number}/permit.pdf",
    summary="Download the permit, with its QR code at 10 cm",
)
def my_permit(
    application_number: str,
    applicant: Applicant = Depends(current_applicant),
    db: Session = Depends(get_db),
) -> Response:
    application = status_service.own_application(db, applicant.session, application_number)
    return _pdf(permit.permit_pdf(application), f"permit_{application.application_number}.pdf")


@router.get(
    "/my/applications/{application_number}/permit-qr.pdf",
    summary="Download only the QR code, large, for the windscreen",
)
def my_permit_qr(
    application_number: str,
    applicant: Applicant = Depends(current_applicant),
    db: Session = Depends(get_db),
) -> Response:
    application = status_service.own_application(db, applicant.session, application_number)
    return _pdf(permit.large_qr_pdf(application), f"permit_qr_{application.application_number}.pdf")
