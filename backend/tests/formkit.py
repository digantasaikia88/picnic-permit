"""Helpers for the application form tests."""

import io
from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import security
from app.core.timeutil import today_local
from app.models import (
    Application,
    DocType,
    InspectionStatus,
    OtpChallenge,
    PoliceStation,
    Role,
    Status,
    User,
    VehicleType,
)
from app.services import dto, otp, uploads, users
from app.services.access import Acting
from app.services.users import OfficeLink
from app.services.validation import REQUIRED_DOCUMENTS
from tests.conftest import PASSWORD, Masters

PDF = b"%PDF-1.4\n% a tiny test document\n%%EOF\n"
MOBILE = "9876543210"


def image_bytes(kind: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (30, 90, 140)).save(buffer, format=kind)
    return buffer.getvalue()


def day(offset: int) -> date:
    """A date `offset` days after today, in the portal's time zone."""
    return today_local() + timedelta(days=offset)


def temp_upload(db: Session, doc_type: DocType, content: bytes = PDF) -> str:
    return uploads.save_temp(
        db, filename=f"{doc_type.value}.pdf", content=content, doc_type=doc_type
    ).token


def payload(db: Session, m: Masters, **overrides: Any) -> dict[str, Any]:
    """A form that passes every rule. Pass a field to change it, or `drop=[...]` to omit keys."""
    drop = overrides.pop("drop", [])
    documents = overrides.pop(
        "documents", {doc.value: temp_upload(db, doc) for doc in REQUIRED_DOCUMENTS}
    )
    vehicle_type_id = db.scalar(select(VehicleType.id).order_by(VehicleType.id).limit(1))
    body: dict[str, Any] = {
        "leader_name": "Rupam Das",
        "leader_age": 34,
        "leader_gender": "MALE",
        "leader_mobile": MOBILE,
        "travel_date": day(10).isoformat(),
        "departure_time": "07:00",
        "return_time": "18:00",
        "origin_address": "Ward 4, Makum Road, Tinsukia",
        "origin_district_id": m.tinsukia.id,
        "origin_police_station_id": m.margherita.id,
        "destination_address": "Dehing riverside, near Digboi",
        "destination_district_id": m.tinsukia.id,
        "destination_police_station_id": None,
        "driving_band": "UP_TO_60",
        "vehicle_reg_number": "AS 23 AB 1234",
        "vehicle_type_id": vehicle_type_id,
        "vehicle_usage": "HIRED",
        "seating_capacity": 17,
        "owner_name": "Bipul Gogoi",
        "owner_mobile": "9876500001",
        "decl_not_goods_vehicle": True,
        "decl_documents_valid": True,
        "decl_no_unpaid_challans": True,
        "driver_name": "Jiten Bora",
        "licence_number": "AS23 20190001234",
        "licence_class": "Transport",
        "licence_valid_until": day(400).isoformat(),
        "driver_mobile": "9876500002",
        "decl_licence_valid": True,
        "decl_no_conviction": True,
        "decl_driver_fit": True,
        "has_handyman": False,
        "handyman_name": "",
        "handyman_mobile": "",
        "members": [
            {"name": "Mitali Das", "age": 31, "gender": "FEMALE"},
            {"name": "Riya Das", "age": 9, "gender": "FEMALE"},
        ],
        "kit_first_aid": True,
        "kit_spare_tyre": True,
        "kit_jack": True,
        "kit_spanner": True,
        "kit_fire_extinguisher": False,
        "emergency_contacts_saved": True,
        "undertaking_accepted": True,
        "documents": documents,
    }
    body.update(overrides)
    for key in drop:
        body.pop(key)
    return body


def new_otp(db: Session, mobile: str = MOBILE) -> tuple[str, str]:
    """Send an OTP and return (otp id, code).

    Earlier OTPs of the number are moved two hours into the past first, so the
    resend wait and the hourly limit do not get in the way of other tests.
    """
    db.execute(
        update(OtpChallenge)
        .where(OtpChallenge.mobile == mobile)
        .values(created_at=OtpChallenge.created_at - timedelta(hours=2))
    )
    challenge, code = otp.request(db, mobile=mobile, purpose=otp.PURPOSE_SUBMIT)
    db.commit()
    return challenge.id, code


def check(client: TestClient, body: dict[str, Any]):
    return client.post("/api/public/applications/check", json=body)


def submit(client: TestClient, db: Session, body: dict[str, Any], *, raise_claim: bool = False):
    otp_id, code = new_otp(db, body["leader_mobile"])
    return client.post(
        "/api/public/applications",
        json={"application": body, "otp_id": otp_id, "otp_code": code, "raise_claim": raise_claim},
    )


# ------------------------------------------------------------- officers

OFFICER = {"officer_name": "A. Baruah", "officer_designation": "Inspector"}


def office_user(db: Session, application: Application, role: Role) -> User:
    """A user of the office that handles this application at the given role's stage.

    The same user is returned on later calls, so a test can log in as it.
    """
    if role == Role.DTO:
        condition = User.dto_office_id == application.dto_office_id
        link = OfficeLink(dto_office=application.dto_office)
    elif role == Role.POLICE_STATION:
        condition = User.police_station_id == application.origin_police_station_id
        link = OfficeLink(police_station=application.origin_police_station)
    else:
        condition = (User.role == Role.DC_OFFICE) & (
            User.district_id == application.origin_district_id
        )
        link = OfficeLink(district=application.origin_district)

    user = db.scalar(select(User).where(User.role == role, condition).order_by(User.id))
    if user is None:
        user, _generated = users.create_user(db, None, role=role, link=link)
        user.password_hash = security.hash_password(PASSWORD)
        user.must_change_password = False
        db.flush()
    return user


ROLE_OF_STAGE = {
    Status.PENDING_DTO: Role.DTO,
    Status.PENDING_POLICE: Role.POLICE_STATION,
    Status.PENDING_DC: Role.DC_OFFICE,
}


def acting_for(db: Session, application: Application) -> Acting:
    """The officer of the office that holds the application now (the DTO if none does)."""
    role = ROLE_OF_STAGE.get(application.status, Role.DTO)
    return Acting(
        user=office_user(db, application, role), name="A. Baruah", designation="Inspector"
    )


def complete_dto_checks(db: Session, application: Application) -> Application:
    """Record the DTO's findings and mark every document, all in order."""
    application.dto_findings = {
        "vahan": {key: "YES" for key in dto.VAHAN_ITEMS},
        "vahan_remarks": "",
        "challans_unpaid": 0,
        "challans_on_record": 0,
        "challan_remarks": "",
        "sarathi": {key: "YES" for key in dto.SARATHI_ITEMS},
        "sarathi_remarks": "",
    }
    for document in application.documents:
        document.verified = True
    db.commit()
    return application


def make_ready(db: Session, application: Application) -> Application:
    """Give an application what each office must record before it can forward:
    the DTO's findings, document check and a passed inspection, and the police
    station's verification with a destination police station.
    """
    complete_dto_checks(db, application)
    application.inspection_status = InspectionStatus.PASSED
    application.police_findings = {
        "driving_time_confirmed": True,
        "verification_remarks": "Verified.",
        "checkpoints": "",
        "comments": "",
    }
    if application.destination_police_station_id is None:
        application.destination_police_station_id = db.scalar(
            select(PoliceStation.id)
            .where(PoliceStation.district_id == application.destination_district_id)
            .order_by(PoliceStation.id)
            .limit(1)
        )
    db.commit()
    return application
