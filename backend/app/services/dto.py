"""The DTO's own work on an application (PRD Section 7.1).

What the office found in VAHAN, in the challan records and in SARATHI; the
check of each uploaded document against the original; and the vehicle
inspection: appointment, checklist, result and certificate.

Nothing here changes the status of an application. The workflow reads the
inspection result when the DTO forwards.
"""

from dataclasses import dataclass
from datetime import date, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError, NotFoundError
from app.core.timeutil import today_local
from app.models import (
    Application,
    ApplicationDocument,
    DocType,
    InspectionStatus,
    Status,
    TempUpload,
)
from app.services import access, audit, sms, uploads, workflow
from app.services.access import Acting

# What the DTO checks in VAHAN, in the order of the SOP.
VAHAN_ITEMS: dict[str, str] = {
    "rc": "Registration certificate",
    "insurance": "Insurance",
    "puc": "Pollution Under Control certificate",
    "tax": "Road tax",
    "fitness": "Fitness",
    "permit": "Permit",
    "seating_capacity": "Seating capacity as declared",
}
# What the DTO checks in SARATHI.
SARATHI_ITEMS: dict[str, str] = {
    "licence_valid": "Licence valid on the travel date",
    "vehicle_class": "Licence covers this class of vehicle",
    "no_suspension": "No suspension",
    "no_convictions": "No disqualifying conviction",
}
ANSWERS = ("YES", "NO", "NOT_CHECKED")

# The inspection checklist of the SOP.
CHECKLIST: dict[str, str] = {
    "brakes": "Brakes",
    "steering": "Steering",
    "tyres": "All tyres, including the spare",
    "lights": "Lights and indicators",
    "horn": "Horn",
    "wipers": "Wipers",
    "mirrors": "Mirrors",
    "seat_belts": "Seat belts",
    "doors": "Doors and emergency exits",
    "sld": "Speed Limiting Device",
}
CHECK_ANSWERS = ("OK", "NOT_OK", "NOT_APPLICABLE")

# The office is warned from this many unpaid challans. It still decides itself.
CHALLAN_WARNING_FROM = 3

INSPECTION_LABELS: dict[InspectionStatus, str] = {
    InspectionStatus.CERTIFICATE_UPLOADED: "Certificate uploaded",
    InspectionStatus.INSPECTION_REQUIRED: "Inspection required",
    InspectionStatus.INSPECTION_SCHEDULED: "Inspection scheduled",
    InspectionStatus.PASSED: "Passed",
    InspectionStatus.FAILED: "Failed",
}


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _require_dto(acting: Acting, application: Application) -> None:
    access.require_holds(acting.user, application)
    if application.status != Status.PENDING_DTO:
        raise DomainError("Only the DTO can record this.")


def _answers(given: dict[str, str], items: dict[str, str], allowed: tuple[str, ...]) -> dict:
    unknown = set(given) - set(items)
    if unknown:
        raise DomainError(f"Unknown item: {sorted(unknown)[0]}.")
    answers = {key: given.get(key, allowed[-1]) for key in items}
    for key, value in answers.items():
        if value not in allowed:
            raise DomainError(f"Choose an answer for: {items[key]}.")
    return answers


def _flat(value: dict[str, Any] | None) -> dict[str, Any]:
    """One level of nesting flattened, so that the change log shows each item."""
    flat: dict[str, Any] = {}
    for key, item in (value or {}).items():
        if isinstance(item, dict):
            flat.update({f"{key}.{inner}": inner_value for inner, inner_value in item.items()})
        else:
            flat[key] = item
    return flat


def _log(
    db: Session,
    application: Application,
    acting: Acting,
    action: str,
    old: dict[str, Any],
    new: dict[str, Any],
) -> bool:
    old_changed, new_changed = audit.changed_fields(old, new)
    if not new_changed:
        return False
    audit.record(
        db,
        actor=acting.user,
        officer_name=acting.name,
        officer_designation=acting.designation,
        action=action,
        entity_type="application",
        entity_id=application.id,
        entity_label=application.application_number,
        old=old_changed or None,
        new=new_changed,
    )
    return True


# ---------------------------------------------------------------- findings


def record_findings(
    db: Session,
    application: Application,
    *,
    acting: Acting,
    vahan: dict[str, str],
    vahan_remarks: str,
    challans_unpaid: int | None,
    challans_on_record: int | None,
    challan_remarks: str,
    sarathi: dict[str, str],
    sarathi_remarks: str,
) -> None:
    """What the DTO found in VAHAN, in the challan records and in SARATHI."""
    _require_dto(acting, application)
    if (
        challans_unpaid is not None
        and challans_on_record is not None
        and challans_unpaid > challans_on_record
    ):
        raise DomainError("Unpaid challans cannot be more than the challans on record.")

    new = {
        "vahan": _answers(vahan, VAHAN_ITEMS, ANSWERS),
        "vahan_remarks": _clean(vahan_remarks),
        "challans_unpaid": challans_unpaid,
        "challans_on_record": challans_on_record,
        "challan_remarks": _clean(challan_remarks),
        "sarathi": _answers(sarathi, SARATHI_ITEMS, ANSWERS),
        "sarathi_remarks": _clean(sarathi_remarks),
    }
    old = application.dto_findings
    application.dto_findings = new
    db.flush()
    _log(db, application, acting, "application.dto_findings", _flat(old), _flat(new))


def challan_warning(application: Application) -> bool:
    unpaid = (application.dto_findings or {}).get("challans_unpaid")
    return unpaid is not None and unpaid >= CHALLAN_WARNING_FROM


def verify_document(
    db: Session,
    application: Application,
    *,
    acting: Acting,
    document_id: int,
    verified: bool | None,
) -> None:
    """The DTO checks one uploaded document against the original."""
    _require_dto(acting, application)
    document = next((d for d in application.documents if d.id == document_id), None)
    if document is None:
        raise NotFoundError("Document not found.")
    old = document.verified
    document.verified = verified
    db.flush()
    key = f"verified.{document.doc_type.value}"
    _log(db, application, acting, "application.document_verified", {key: old}, {key: verified})


# -------------------------------------------------------------- inspection


def schedule_inspection(
    db: Session, application: Application, *, acting: Acting, on: date, at: time, place: str
) -> None:
    """The DTO fixes the inspection. The applicant is asked by SMS to bring the vehicle."""
    _require_dto(acting, application)
    if application.inspection_status == InspectionStatus.PASSED:
        raise DomainError("The vehicle has already passed inspection.")
    place = _clean(place)
    if not place:
        raise DomainError("Enter the place of inspection.")
    if on < today_local():
        raise DomainError("The inspection date cannot be in the past.")
    if on > application.travel_date:
        raise DomainError("The inspection date cannot be after the travel date.")

    old_status = application.inspection_status
    old = application.inspection or {}
    # A new appointment starts afresh: an earlier result stays in the change log.
    new = {
        "scheduled_date": on.isoformat(),
        "scheduled_time": at.strftime("%H:%M"),
        "place": place,
    }
    application.inspection = new
    application.inspection_status = InspectionStatus.INSPECTION_SCHEDULED
    db.flush()
    _log(
        db,
        application,
        acting,
        "application.inspection_scheduled",
        {**{key: old.get(key) for key in new}, "inspection_status": old_status.value},
        {**new, "inspection_status": InspectionStatus.INSPECTION_SCHEDULED.value},
    )
    hour = at.strftime("%I:%M %p").lstrip("0")
    sms.send(
        db,
        mobile=application.leader_mobile,
        kind=sms.KIND_INSPECTION_SCHEDULED,
        application=application,
        message=(
            f"Picnic Portal: bring vehicle {application.vehicle_reg_number} of application "
            f"{application.application_number} for inspection on {on.strftime('%d-%m-%Y')} at "
            f"{hour}, at {place}. Bring the original documents."
        ),
    )


def record_inspection(
    db: Session,
    application: Application,
    *,
    acting: Acting,
    checklist: dict[str, str],
    inspected_on: date,
    inspecting_officer: str,
    passed: bool,
    remarks: str,
) -> None:
    """The Motor Vehicle Inspector's checklist and result."""
    _require_dto(acting, application)
    inspecting_officer = _clean(inspecting_officer)
    remarks = _clean(remarks)
    if not inspecting_officer:
        raise DomainError("Enter the name of the inspecting officer.")
    if inspected_on > today_local():
        raise DomainError("The inspection date cannot be in the future.")
    if inspected_on < application.submission_date:
        raise DomainError("The inspection date cannot be before the application was submitted.")
    missing = [label for key, label in CHECKLIST.items() if checklist.get(key) is None]
    if missing:
        raise DomainError(f"Mark every item of the checklist. Not marked: {missing[0]}.")
    answers = _answers(checklist, CHECKLIST, CHECK_ANSWERS)
    not_ok = [CHECKLIST[key] for key, value in answers.items() if value == "NOT_OK"]
    if passed and not_ok:
        raise DomainError(
            f"The vehicle cannot pass while an item is not in order: {', '.join(not_ok)}."
        )
    if not passed and not not_ok and not remarks:
        raise DomainError("Mark what is not in order, or write why the vehicle failed.")

    result = InspectionStatus.PASSED if passed else InspectionStatus.FAILED
    old_status = application.inspection_status
    old = application.inspection or {}
    new = {
        **{key: old.get(key) for key in ("scheduled_date", "scheduled_time", "place")},
        "checklist": answers,
        "inspected_on": inspected_on.isoformat(),
        "inspecting_officer": inspecting_officer,
        "remarks": remarks,
    }
    application.inspection = new
    application.inspection_status = result
    db.flush()
    _log(
        db,
        application,
        acting,
        "application.inspection_recorded",
        {**_flat(old), "inspection_status": old_status.value},
        {**_flat(new), "inspection_status": result.value},
    )
    outcome = (
        "PASSED inspection"
        if passed
        else "did NOT pass inspection" + (f": {', '.join(not_ok)}" if not_ok else "")
    )
    sms.send(
        db,
        mobile=application.leader_mobile,
        kind=sms.KIND_INSPECTION_RESULT,
        application=application,
        message=(
            f"Picnic Portal: vehicle {application.vehicle_reg_number} of application "
            f"{application.application_number} {outcome}. Status: {workflow.status_url()}"
        ),
    )


# ------------------------------------------------------------- certificate


@dataclass(frozen=True)
class EarlierCertificate:
    document: ApplicationDocument
    application: Application
    # True when the DTO of that application confirmed this very file.
    confirmed: bool


def earlier_certificates(db: Session, application: Application) -> list[EarlierCertificate]:
    """Inspection certificates already on record for the same vehicle, newest first."""
    rows = db.execute(
        select(ApplicationDocument, Application)
        .join(Application, ApplicationDocument.application_id == Application.id)
        .where(
            Application.vehicle_reg_key == application.vehicle_reg_key,
            Application.id != application.id,
            ApplicationDocument.doc_type == DocType.INSPECTION_CERTIFICATE,
        )
        .order_by(ApplicationDocument.uploaded_at.desc(), ApplicationDocument.id.desc())
        .limit(10)
    )
    return [
        EarlierCertificate(
            document=document,
            application=other,
            confirmed=other.certificate_confirmed_doc_id == document.id,
        )
        for document, other in rows
    ]


def certificate_for(db: Session, application: Application, document_id: int) -> ApplicationDocument:
    """A certificate the DTO may confirm: this application's own, or one of the same vehicle."""
    document = db.get(ApplicationDocument, document_id)
    if (
        document is None
        or document.doc_type != DocType.INSPECTION_CERTIFICATE
        or document.application.vehicle_reg_key != application.vehicle_reg_key
    ):
        raise NotFoundError("Inspection certificate not found.")
    return document


def confirm_certificate(
    db: Session, application: Application, *, acting: Acting, document_id: int | None
) -> None:
    """The DTO confirms an inspection certificate, or takes the confirmation back."""
    _require_dto(acting, application)
    old_label = None
    if application.certificate_confirmed_doc_id is not None:
        old = db.get(ApplicationDocument, application.certificate_confirmed_doc_id)
        old_label = old.application.application_number if old else None

    new_label = None
    if document_id is not None:
        document = certificate_for(db, application, document_id)
        new_label = document.application.application_number
    application.certificate_confirmed_doc_id = document_id
    db.flush()
    _log(
        db,
        application,
        acting,
        "application.certificate_confirmed",
        {"confirmed_certificate_of": old_label},
        {"confirmed_certificate_of": new_label},
    )


def upload_certificate(
    db: Session,
    application: Application,
    *,
    acting: Acting,
    upload: TempUpload,
    notify: bool = True,
) -> None:
    """The DTO office uploads the inspection certificate itself.

    The file takes the place of any certificate already on the application and
    shows with its other documents. The office vouches for a file it uploads,
    so the certificate counts as confirmed. The applicant is told by SMS.
    """
    _require_dto(acting, application)
    old_names = [
        d.original_name
        for d in application.documents
        if d.doc_type == DocType.INSPECTION_CERTIFICATE
    ]
    old_status = application.inspection_status
    uploads.replace(db, application, {DocType.INSPECTION_CERTIFICATE: upload})
    # A result already recorded stays. Otherwise the certificate is now on the application.
    if application.inspection_status in (
        InspectionStatus.INSPECTION_REQUIRED,
        InspectionStatus.INSPECTION_SCHEDULED,
    ):
        application.inspection_status = InspectionStatus.CERTIFICATE_UPLOADED
    db.flush()
    db.refresh(application)
    document = next(
        d for d in application.documents if d.doc_type == DocType.INSPECTION_CERTIFICATE
    )
    application.certificate_confirmed_doc_id = document.id
    db.flush()
    audit.record(
        db,
        actor=acting.user,
        officer_name=acting.name,
        officer_designation=acting.designation,
        action="application.inspection_certificate_uploaded_by_office",
        entity_type="application",
        entity_id=application.id,
        entity_label=application.application_number,
        old={
            "inspection_status": old_status.value,
            "file": old_names[0] if old_names else None,
            "certificate_confirmed": False,
        },
        new={
            "inspection_status": application.inspection_status.value,
            "file": document.original_name,
            "certificate_confirmed": True,
        },
    )
    if not notify:
        # Uploaded together with the inspection result, which has its own SMS.
        return
    sms.send(
        db,
        mobile=application.leader_mobile,
        kind=sms.KIND_CORRECTED,
        application=application,
        message=(
            f"Picnic Portal: {application.dto_office.name} uploaded the inspection certificate "
            f"of vehicle {application.vehicle_reg_number} to application "
            f"{application.application_number}. Status: {workflow.status_url()}"
        ),
    )
