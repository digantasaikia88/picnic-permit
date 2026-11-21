"""The hard rules of the application form (PRD Section 4 and Section 6).

Every rule is enforced here, in the backend. The form in the browser repeats
them only for the applicant's convenience. The numbers (7 days, 07:00, 18:00
and so on) are read from the settings, never written into the code.
"""

import re
from dataclasses import dataclass
from datetime import date, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import FormError
from app.models import (
    District,
    DocType,
    DrivingBand,
    DtoOffice,
    PicnicSeason,
    PoliceStation,
    TempUpload,
    VehicleType,
)
from app.schemas.application import ApplicationIn
from app.services import duplicates, uploads
from app.services import settings as app_settings

_MOBILE_RE = re.compile(r"^[6-9][0-9]{9}$")
_ALNUM_RE = re.compile(r"^[A-Z0-9]+$")
_MAX_AGE = 120
_MAX_SEATS = 100

DOCUMENT_LABELS: dict[DocType, str] = {
    DocType.RC: "Registration Certificate (RC)",
    DocType.INSURANCE: "Insurance",
    DocType.PUC: "Pollution Under Control (PUC)",
    DocType.VEHICLE_PERMIT: "Vehicle permit",
    DocType.SLD_CERTIFICATE: "Speed Limiting Device certificate",
    DocType.INSPECTION_CERTIFICATE: (
        "Fitness and physical inspection certificate for the current year "
        "for Picnic/Recreational Journey"
    ),
    DocType.OWNER_SELF_CERTIFICATE: "Owner's signed self-certificate",
    DocType.DRIVING_LICENCE: "Copy of driving licence",
}

REQUIRED_DOCUMENTS = frozenset(
    {
        DocType.RC,
        DocType.INSURANCE,
        DocType.PUC,
        DocType.OWNER_SELF_CERTIFICATE,
        DocType.DRIVING_LICENCE,
    }
)

# Ticks that must all be given. The fire extinguisher is "where available" in the SOP.
REQUIRED_TICKS: dict[str, str] = {
    "decl_not_goods_vehicle": "Please confirm this.",
    "decl_documents_valid": "Please confirm this.",
    "decl_no_unpaid_challans": "Please confirm this.",
    "decl_licence_valid": "Please confirm this.",
    "decl_no_conviction": "Please confirm this.",
    "decl_driver_fit": "Please confirm this.",
    "kit_first_aid": "This item must be carried.",
    "kit_spare_tyre": "This item must be carried.",
    "kit_jack": "This item must be carried.",
    "kit_spanner": "This item must be carried.",
    "emergency_contacts_saved": "Please confirm this.",
    "undertaking_accepted": "Please accept the undertaking.",
}
OPTIONAL_TICKS = ("kit_fire_extinguisher",)


@dataclass(frozen=True)
class TravelWindow:
    """The dates and hours an application may ask for, for a given submission date."""

    earliest_date: date
    latest_date: date
    earliest_departure: time
    latest_return: time
    season_start: date | None
    season_end: date | None


def get_season(db: Session) -> PicnicSeason:
    season = db.get(PicnicSeason, 1)
    if season is None:
        season = PicnicSeason(id=1)
        db.add(season)
        db.flush()
    return season


def travel_window(db: Session, submission_date: date) -> TravelWindow:
    min_days = app_settings.get_int(db, app_settings.MIN_DAYS_BEFORE_TRAVEL)
    max_days = app_settings.get_int(db, app_settings.MAX_DAYS_BEFORE_TRAVEL)
    season = get_season(db)
    has_season = season.start_date is not None and season.end_date is not None
    return TravelWindow(
        earliest_date=submission_date + timedelta(days=min_days),
        latest_date=submission_date + timedelta(days=max_days),
        earliest_departure=time(app_settings.get_int(db, app_settings.EARLIEST_DEPARTURE_HOUR)),
        latest_return=time(app_settings.get_int(db, app_settings.LATEST_RETURN_HOUR)),
        season_start=season.start_date if has_season else None,
        season_end=season.end_date if has_season else None,
    )


def _clock(value: time) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def _day(value: date) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def count_people(data: ApplicationIn, *, child_free_below_age: int) -> int:
    """People counted against the seats: leader, members, driver and handyman.

    A child younger than `child_free_below_age` is not counted. With the
    starting value 0, everyone counts.
    """
    ages = [data.leader_age, *(member.age for member in data.members)]
    counted = sum(1 for age in ages if age >= child_free_below_age)
    return counted + 1 + (1 if data.has_handyman else 0)


@dataclass(frozen=True)
class Validated:
    """A form that passed every rule, with the master rows it refers to."""

    data: ApplicationIn
    origin_district: District
    origin_police_station: PoliceStation
    dto_office: DtoOffice
    destination_district: District
    destination_police_station: PoliceStation | None
    vehicle_type: VehicleType
    vehicle_reg_number: str
    licence_number: str
    total_people: int
    uploads: dict[DocType, TempUpload]


def validate(
    db: Session,
    data: ApplicationIn,
    *,
    submission_date: date,
    existing_documents: frozenset[DocType] | set[DocType] = frozenset(),
) -> Validated:
    """Apply every rule. Raises FormError with one message per field that fails.

    `existing_documents` are the documents an application already has, when it
    is being corrected: they need not be uploaded again.
    """
    errors: dict[str, str] = {}

    def need(field: str, value: str, what: str) -> None:
        if not value:
            errors[field] = f"Enter {what}."

    def mobile(field: str, value: str, whose: str) -> None:
        if not _MOBILE_RE.fullmatch(value):
            errors[field] = f"Enter {whose} 10-digit mobile number."

    def age(field: str, value: int) -> None:
        if not 0 <= value <= _MAX_AGE:
            errors[field] = f"Enter an age from 0 to {_MAX_AGE}."

    # ------------------------------------------------------ step 1: the leader
    need("leader_name", data.leader_name, "the group leader's full name")
    mobile("leader_mobile", data.leader_mobile, "the group leader's")
    leader_min_age = app_settings.get_int(db, app_settings.LEADER_MIN_AGE)
    if data.leader_age < leader_min_age:
        errors["leader_age"] = f"The group leader must be at least {leader_min_age} years old."
    else:
        age("leader_age", data.leader_age)

    # ----------------------------------------------------- step 1: the journey
    window = travel_window(db, submission_date)
    min_days = app_settings.get_int(db, app_settings.MIN_DAYS_BEFORE_TRAVEL)
    max_days = app_settings.get_int(db, app_settings.MAX_DAYS_BEFORE_TRAVEL)
    if data.travel_date < window.earliest_date:
        errors["travel_date"] = (
            f"The date of travel must be at least {min_days} days from the date of application. "
            f"The earliest date is {_day(window.earliest_date)}."
        )
    elif data.travel_date > window.latest_date:
        errors["travel_date"] = (
            f"The date of travel cannot be more than {max_days} days from the date of "
            f"application. The latest date is {_day(window.latest_date)}."
        )
    elif window.season_start and not window.season_start <= data.travel_date <= window.season_end:
        errors["travel_date"] = (
            f"The picnic season is from {_day(window.season_start)} to "
            f"{_day(window.season_end)}. Choose a date of travel in the season."
        )

    if data.departure_time < window.earliest_departure:
        errors["departure_time"] = (
            f"The journey cannot begin before {_clock(window.earliest_departure)}."
        )
    if data.return_time > window.latest_return:
        errors["return_time"] = f"The group must return by {_clock(window.latest_return)}."
    elif data.return_time <= data.departure_time:
        errors["return_time"] = "The return time must be later than the departure time."

    need("origin_address", data.origin_address, "the full address of the starting point")
    origin_district = db.get(District, data.origin_district_id)
    origin_station = db.get(PoliceStation, data.origin_police_station_id)
    dto_office: DtoOffice | None = None
    if origin_district is None or not origin_district.is_active:
        errors["origin_district_id"] = "Choose the district of the starting point."
    else:
        dto_office = db.scalar(
            select(DtoOffice)
            .where(DtoOffice.district_id == origin_district.id, DtoOffice.is_active)
            .order_by(DtoOffice.id)
        )
        if dto_office is None:
            errors["origin_district_id"] = (
                "Applications from this district cannot be accepted yet. "
                "No DTO office is set up for it."
            )
        if (
            origin_station is None
            or not origin_station.is_active
            or origin_station.district_id != origin_district.id
        ):
            errors["origin_police_station_id"] = "Choose a police station of the selected district."

    # ------------------------------------------------------ step 2: destination
    need("destination_address", data.destination_address, "the full address of the picnic spot")
    destination_district = db.get(District, data.destination_district_id)
    destination_station: PoliceStation | None = None
    if destination_district is None or not destination_district.is_active:
        errors["destination_district_id"] = "Choose the district of the picnic spot."
    elif data.destination_police_station_id is not None:
        destination_station = db.get(PoliceStation, data.destination_police_station_id)
        if (
            destination_station is None
            or not destination_station.is_active
            or destination_station.district_id != destination_district.id
        ):
            errors["destination_police_station_id"] = (
                "Choose a police station of the selected district, or leave it as Not sure."
            )

    # ---------------------------------------------------------- step 3: vehicle
    reg_number = duplicates.stored_form(data.vehicle_reg_number)
    reg_key = duplicates.comparison_key(data.vehicle_reg_number)
    if not 5 <= len(reg_key) <= 12 or not _ALNUM_RE.fullmatch(reg_key):
        errors["vehicle_reg_number"] = (
            "Enter the registration number as on the Registration Certificate, "
            "for example AS01AB1234."
        )
    vehicle_type = db.get(VehicleType, data.vehicle_type_id)
    if vehicle_type is None or not vehicle_type.is_active:
        errors["vehicle_type_id"] = "Choose the type of vehicle."
    if not 1 <= data.seating_capacity <= _MAX_SEATS:
        errors["seating_capacity"] = (
            f"Enter the registered seating capacity, from 1 to {_MAX_SEATS}."
        )
    need("owner_name", data.owner_name, "the owner's name")
    mobile("owner_mobile", data.owner_mobile, "the owner's")

    # ----------------------------------------------- step 4: driver and handyman
    need("driver_name", data.driver_name, "the driver's full name")
    licence_number = duplicates.stored_form(data.licence_number)
    licence_key = duplicates.comparison_key(data.licence_number)
    if not 5 <= len(licence_key) <= 20 or not _ALNUM_RE.fullmatch(licence_key):
        errors["licence_number"] = "Enter the driving licence number as printed on the licence."
    need("licence_class", data.licence_class, "the vehicle class on the licence")
    if data.licence_valid_until < data.travel_date:
        errors["licence_valid_until"] = "The licence must be valid on the date of travel."
    mobile("driver_mobile", data.driver_mobile, "the driver's")
    if data.has_handyman:
        need("handyman_name", data.handyman_name, "the handyman's name")
        mobile("handyman_mobile", data.handyman_mobile, "the handyman's")

    # ------------------------------------------------------- step 5: passengers
    for index, member in enumerate(data.members):
        if not member.name:
            errors[f"members.{index}.name"] = "Enter the passenger's full name."
        age(f"members.{index}.age", member.age)

    total_people = count_people(
        data, child_free_below_age=app_settings.get_int(db, app_settings.CHILD_FREE_BELOW_AGE)
    )
    if "seating_capacity" not in errors and total_people > data.seating_capacity:
        errors["members"] = (
            f"{total_people} people are travelling, counting the group leader, members, driver "
            f"and handyman, but the vehicle has {data.seating_capacity} seats. "
            "Remove passengers or correct the seating capacity."
        )

    # ------------------------------------------------- ticks of steps 3, 4 and 6
    for field, message in REQUIRED_TICKS.items():
        if not getattr(data, field):
            errors[field] = message

    # ---------------------------------------------------------------- documents
    found: dict[DocType, TempUpload] = {}
    for doc_type, token in data.documents.items():
        if doc_type not in DOCUMENT_LABELS:
            # A document the form no longer asks for is simply not taken.
            continue
        upload = uploads.get_temp(db, token)
        if upload is None or upload.doc_type != doc_type:
            errors[f"documents.{doc_type.value}"] = (
                "This file is no longer available. Please upload it again."
            )
        else:
            found[doc_type] = upload
    for doc_type in REQUIRED_DOCUMENTS:
        if doc_type not in data.documents and doc_type not in existing_documents:
            errors[f"documents.{doc_type.value}"] = "Please upload this document."

    if errors:
        raise FormError(errors)

    assert origin_district and origin_station and dto_office  # noqa: S101
    assert destination_district and vehicle_type  # noqa: S101
    return Validated(
        data=data,
        origin_district=origin_district,
        origin_police_station=origin_station,
        dto_office=dto_office,
        destination_district=destination_district,
        destination_police_station=destination_station,
        vehicle_type=vehicle_type,
        vehicle_reg_number=reg_number,
        licence_number=licence_number,
        total_people=total_people,
        uploads=found,
    )


def driving_band_needs_dc_approval(band: DrivingBand) -> bool:
    """60 to 90 minutes is considered only with the DC's specific approval."""
    return band == DrivingBand.FROM_60_TO_90
