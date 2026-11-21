"""Checking, submitting and correcting an application (PRD Sections 5, 6, 7.4 and 10)."""

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, DomainError, FormError, TooManyRequestsError
from app.core.timeutil import now_utc, today_local
from app.models import (
    Application,
    ApplicationPassenger,
    ApplicationSequence,
    District,
    DocType,
    InspectionStatus,
    Status,
)
from app.schemas.application import ApplicationIn, CheckResult, DuplicateInfo
from app.services import (
    access,
    audit,
    duplicates,
    flags,
    otp,
    sms,
    uploads,
    validation,
    workflow,
)
from app.services import settings as app_settings
from app.services.access import Acting

_TICKS = (*validation.REQUIRED_TICKS, *validation.OPTIONAL_TICKS)

# Form fields copied to the application as they are.
_PLAIN_FIELDS = (
    "leader_name",
    "leader_age",
    "leader_gender",
    "leader_mobile",
    "travel_date",
    "departure_time",
    "return_time",
    "origin_address",
    "destination_address",
    "driving_band",
    "vehicle_usage",
    "seating_capacity",
    "owner_name",
    "owner_mobile",
    "driver_name",
    "licence_class",
    "licence_valid_until",
    "driver_mobile",
    "has_handyman",
)


def _duplicate_info(found: duplicates.Duplicates) -> DuplicateInfo | None:
    if not found:
        return None
    if found.vehicle and found.driver:
        what = "this vehicle and this driver"
    elif found.vehicle:
        what = "this vehicle"
    else:
        what = "this driver"
    return DuplicateInfo(
        vehicle=bool(found.vehicle),
        driver=bool(found.driver),
        message=f"An application already exists for {what} on that date.",
    )


def _find_duplicates(
    db: Session, valid: validation.Validated, *, exclude: Application | None = None
) -> duplicates.Duplicates:
    return duplicates.find(
        db,
        vehicle_reg_number=valid.vehicle_reg_number,
        licence_number=valid.licence_number,
        travel_date=valid.data.travel_date,
        exclude_application_id=exclude.id if exclude else None,
    )


def check(db: Session, data: ApplicationIn) -> CheckResult:
    """Validate the whole form and run the duplicate check, without saving anything."""
    valid = validation.validate(db, data, submission_date=today_local())
    return CheckResult(
        total_people=valid.total_people, duplicate=_duplicate_info(_find_duplicates(db, valid))
    )


def next_application_number(db: Session, district: District, on: date) -> str:
    """11 digits: 2-digit year, 4-digit District ID, 5-digit serial for that district and year."""
    sequence = db.scalar(
        select(ApplicationSequence)
        .where(
            ApplicationSequence.year == on.year, ApplicationSequence.district_code == district.code
        )
        .with_for_update()
    )
    if sequence is None:
        sequence = ApplicationSequence(year=on.year, district_code=district.code, last_serial=0)
        db.add(sequence)
    sequence.last_serial += 1
    db.flush()
    return f"{on.year % 100:02d}{district.code:04d}{sequence.last_serial:05d}"


def snapshot(application: Application) -> dict[str, Any]:
    """The applicant-entered content of an application, for the change log."""
    values: dict[str, Any] = {name: getattr(application, name) for name in _PLAIN_FIELDS}
    values.update(
        origin_district_id=application.origin_district_id,
        origin_police_station_id=application.origin_police_station_id,
        destination_district_id=application.destination_district_id,
        destination_police_station_id=application.destination_police_station_id,
        vehicle_reg_number=application.vehicle_reg_number,
        vehicle_type_id=application.vehicle_type_id,
        licence_number=application.licence_number,
        handyman_name=application.handyman_name,
        handyman_mobile=application.handyman_mobile,
        passengers=[
            {"name": p.name, "age": p.age, "gender": p.gender.value}
            for p in application.passengers
            if not p.is_group_leader
        ],
    )
    # JSON-friendly values: dates, times and enums as text.
    return {
        key: value
        if isinstance(value, (int, str, bool, list)) or value is None
        else str(getattr(value, "value", value))
        for key, value in values.items()
    }


def _fill(application: Application, valid: validation.Validated) -> None:
    """Copy a validated form onto an application (new or being corrected)."""
    data = valid.data
    for name in _PLAIN_FIELDS:
        setattr(application, name, getattr(data, name))

    application.origin_district_id = valid.origin_district.id
    application.origin_police_station_id = valid.origin_police_station.id
    application.dto_office_id = valid.dto_office.id
    application.destination_district_id = valid.destination_district.id
    application.destination_police_station_id = (
        valid.destination_police_station.id if valid.destination_police_station else None
    )
    application.needs_dc_specific_approval = validation.driving_band_needs_dc_approval(
        data.driving_band
    )
    application.vehicle_reg_number = valid.vehicle_reg_number
    application.vehicle_reg_key = duplicates.comparison_key(valid.vehicle_reg_number)
    application.vehicle_type_id = valid.vehicle_type.id
    application.licence_number = valid.licence_number
    application.licence_key = duplicates.comparison_key(valid.licence_number)
    application.handyman_name = data.handyman_name if data.has_handyman else None
    application.handyman_mobile = data.handyman_mobile if data.has_handyman else None
    application.declarations = {tick: bool(getattr(data, tick)) for tick in _TICKS}
    application.total_people = valid.total_people

    # The group leader is always passenger 1.
    application.passengers = [
        ApplicationPassenger(
            position=1,
            name=data.leader_name,
            age=data.leader_age,
            gender=data.leader_gender,
            is_group_leader=True,
        ),
        *(
            ApplicationPassenger(
                position=index, name=member.name, age=member.age, gender=member.gender
            )
            for index, member in enumerate(data.members, start=2)
        ),
    ]


def submit(
    db: Session,
    data: ApplicationIn,
    *,
    otp_id: str,
    otp_code: str,
    raise_claim: bool,
) -> Application:
    """Submit an application. The caller commits.

    Order matters: the rules and the duplicate check come first, so a wrong
    form never uses up the OTP; the OTP comes last, just before saving.
    """
    today = today_local()
    valid = validation.validate(db, data, submission_date=today)
    flags.refuse_if_blocked(db, data.leader_mobile)

    found = _find_duplicates(db, valid)
    info = _duplicate_info(found)
    if info and not raise_claim:
        error = ConflictError(info.message)
        error.extra = {"duplicate": info.model_dump()}
        raise error
    is_claim = bool(found) and raise_claim

    limit = app_settings.get_int(db, app_settings.APPLICATIONS_PER_MOBILE_PER_DAY)
    submitted_today = db.scalar(
        select(func.count())
        .select_from(Application)
        .where(
            Application.leader_mobile == data.leader_mobile, Application.submission_date == today
        )
    )
    if (submitted_today or 0) >= limit:
        raise TooManyRequestsError(
            f"This mobile number has already submitted {limit} applications today. "
            "Please try again tomorrow."
        )

    challenge = otp.verify(
        db, otp_id=otp_id, mobile=data.leader_mobile, purpose=otp.PURPOSE_SUBMIT, code=otp_code
    )

    application = Application(
        application_number=next_application_number(db, valid.origin_district, today),
        submitted_at=now_utc(),
        submission_date=today,
        inspection_status=(
            InspectionStatus.CERTIFICATE_UPLOADED
            if DocType.INSPECTION_CERTIFICATE in valid.uploads
            else InspectionStatus.INSPECTION_REQUIRED
        ),
        is_duplicate_claim=is_claim,
    )
    _fill(application, valid)
    db.add(application)

    workflow.submit(db, application, is_duplicate_claim=is_claim)
    uploads.attach(db, application, valid.uploads)
    otp.consume(challenge)
    db.flush()
    return application


# Labels of the form fields, for the SMS that tells the applicant what an officer changed.
FIELD_LABELS: dict[str, str] = {
    "leader_name": "group leader's name",
    "leader_age": "group leader's age",
    "leader_gender": "group leader's gender",
    "travel_date": "date of travel",
    "departure_time": "departure time",
    "return_time": "return time",
    "origin_address": "starting point",
    "origin_district_id": "district of starting point",
    "origin_police_station_id": "police station of starting point",
    "destination_address": "picnic spot",
    "destination_district_id": "destination district",
    "destination_police_station_id": "destination police station",
    "driving_band": "driving time",
    "vehicle_reg_number": "vehicle registration number",
    "vehicle_type_id": "type of vehicle",
    "vehicle_usage": "private or hired",
    "seating_capacity": "seating capacity",
    "owner_name": "owner's name",
    "owner_mobile": "owner's mobile number",
    "driver_name": "driver's name",
    "licence_number": "driving licence number",
    "licence_class": "licence class",
    "licence_valid_until": "licence validity",
    "driver_mobile": "driver's mobile number",
    "has_handyman": "handyman",
    "handyman_name": "handyman's name",
    "handyman_mobile": "handyman's mobile number",
    "passengers": "passenger list",
    "documents_replaced": "documents",
}


@dataclass(frozen=True)
class CorrectionResult:
    old: dict[str, Any]
    new: dict[str, Any]
    vehicle_or_driver_changed: bool
    district_changed: bool

    @property
    def changed_labels(self) -> list[str]:
        return [FIELD_LABELS.get(key, key) for key in self.new]


def _apply_correction(
    db: Session, application: Application, data: ApplicationIn, *, lock_district: bool
) -> CorrectionResult:
    """Validate corrected data and write it onto the application (PRD Section 7.4).

    - The form rules apply, and the minimum and maximum days count from the
      original submission date.
    - The group leader's mobile number is never changed: the OTP is tied to it.
    - Documents already on the application stay unless a new file replaces them.
    - A clash with another application counts only where the vehicle, the
      driver or the date is changed.
    """
    locked: dict[str, str] = {}
    if data.leader_mobile != application.leader_mobile:
        locked["leader_mobile"] = "The group leader's mobile number cannot be changed."
    if lock_district and data.origin_district_id != application.origin_district_id:
        locked["origin_district_id"] = "The district of the starting point cannot be changed."
    if locked:
        raise FormError(locked)

    existing = {document.doc_type for document in application.documents}
    valid = validation.validate(
        db, data, submission_date=application.submission_date, existing_documents=existing
    )

    # The application already holds its vehicle and driver for its travel date.
    # Otherwise a duplicate claim raised against it (on hold with the DTO)
    # would stop any correction at all.
    found = _find_duplicates(db, valid, exclude=application)
    date_changed = data.travel_date != application.travel_date
    vehicle_changed = (
        duplicates.comparison_key(valid.vehicle_reg_number) != application.vehicle_reg_key
    )
    driver_changed = duplicates.comparison_key(valid.licence_number) != application.licence_key
    info = _duplicate_info(
        duplicates.Duplicates(
            vehicle=found.vehicle if (vehicle_changed or date_changed) else [],
            driver=found.driver if (driver_changed or date_changed) else [],
        )
    )
    if info:
        error = ConflictError(info.message)
        error.extra = {"duplicate": info.model_dump()}
        raise error

    before = snapshot(application)
    district_changed = valid.origin_district.id != application.origin_district_id
    # Remove the old passenger rows first: positions are unique per application.
    application.passengers.clear()
    db.flush()
    _fill(application, valid)
    db.flush()
    after = snapshot(application)

    # What the DTO found was about the old vehicle or driver: it has to be checked again.
    if vehicle_changed:
        application.inspection = None
        application.inspection_status = InspectionStatus.INSPECTION_REQUIRED
        application.certificate_confirmed_doc_id = None
    if vehicle_changed or driver_changed:
        application.dto_findings = None

    replaced = sorted(doc_type.value for doc_type in valid.uploads)
    uploads.replace(db, application, valid.uploads)
    if DocType.INSPECTION_CERTIFICATE in valid.uploads and application.inspection_status in (
        InspectionStatus.INSPECTION_REQUIRED,
        InspectionStatus.INSPECTION_SCHEDULED,
    ):
        application.inspection_status = InspectionStatus.CERTIFICATE_UPLOADED

    old, new = audit.changed_fields(before, after)
    if replaced:
        new["documents_replaced"] = replaced
    return CorrectionResult(
        old=old,
        new=new,
        vehicle_or_driver_changed=vehicle_changed or driver_changed,
        district_changed=district_changed,
    )


def correct(db: Session, application: Application, data: ApplicationIn) -> Application:
    """The applicant corrects a returned application and resubmits it. The caller commits.

    The applicant cannot change the district of the starting point.
    """
    if application.status != Status.RETURNED_TO_APPLICANT:
        raise DomainError("Only an application returned for correction can be corrected.")

    result = _apply_correction(db, application, data, lock_district=True)
    audit.record(
        db,
        actor=None,
        system_label=workflow.APPLICANT,
        action="application.corrected_by_applicant",
        entity_type="application",
        entity_id=application.id,
        entity_label=application.application_number,
        old=result.old or None,
        new=result.new or None,
    )
    workflow.resubmit(db, application, vehicle_or_driver_changed=result.vehicle_or_driver_changed)
    db.flush()
    return application


def correct_by_officer(
    db: Session, application: Application, data: ApplicationIn, *, acting: Acting
) -> CorrectionResult:
    """The office that holds an application corrects its data or documents itself.

    Every change is logged with the officer, the old value and the new value,
    and the applicant is told by SMS what was changed.

    If the district of the starting point is changed, the application moves to
    the DTO of the new district. If the vehicle or the driver is changed after
    the DTO stage, it goes back to the DTO. The caller commits.
    """
    access.require_holds(acting.user, application)
    office = workflow.office_name(application) or "the office"

    result = _apply_correction(db, application, data, lock_district=False)
    if not result.new:
        raise DomainError("Nothing was changed.")

    audit.record(
        db,
        actor=acting.user,
        officer_name=acting.name,
        officer_designation=acting.designation,
        action="application.corrected_by_officer",
        entity_type="application",
        entity_id=application.id,
        entity_label=application.application_number,
        old=result.old or None,
        new=result.new,
    )

    moved = ""
    if application.status != Status.PENDING_DTO and (
        result.district_changed or result.vehicle_or_driver_changed
    ):
        why = (
            "The district of the starting point was changed."
            if result.district_changed
            else "The vehicle or driver was changed."
        )
        workflow.send_back_to_dto(db, application, acting=acting, why=why)
        # Reload, so that the office named below is the new district's DTO.
        db.flush()
        db.refresh(application)
        moved = f" It is now with {workflow.office_name(application)}."
    elif result.district_changed:
        # Already at the DTO stage: it moves to the queue of the new district's DTO.
        application.working_status_id = None
        db.flush()
        db.refresh(application)
        moved = f" It is now with {workflow.office_name(application)}."

    sms.send(
        db,
        mobile=application.leader_mobile,
        kind=sms.KIND_CORRECTED,
        application=application,
        message=(
            f"Picnic Portal: application {application.application_number} was corrected by "
            f"{office}. Changed: {', '.join(result.changed_labels)}.{moved} "
            f"Status: {workflow.status_url()}"
        ),
    )
    db.flush()
    return result
