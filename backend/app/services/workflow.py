"""The application workflow: one state machine, and the only place a status changes.

    submit ──> PENDING_DTO ──> PENDING_POLICE ──> PENDING_DC ──> APPROVED
       │           │                 │                │
       │           └─────────────────┴────────────────┴──> RETURNED_TO_APPLICANT
       │                                                          │ resubmit
       │                         back to the office that returned it
       │
       └─────> ON_HOLD_DUPLICATE_CLAIM  (blocked by the duplicate check; a claim was raised)

Built so far: submission (Phase 3), return and resubmission (Phase 4), forward,
approve, reject, sending back to the DTO, transfer between police stations and
duplicate claims (Phase 5), the permit on approval and expiry (Phase 6). Cancel
and restore come in Phase 7, in this file.

Every transition writes an audit row and sends an SMS to the group leader.
"""

import secrets
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.timeutil import now_utc
from app.models import (
    Application,
    ApplicationDocument,
    DocType,
    InspectionStatus,
    PoliceStation,
    Status,
)
from app.services import access, audit, sms
from app.services.access import Acting

APPLICANT = "applicant"

# The three offices an application waits at. Each can return it to the applicant.
PENDING_STATUSES = (Status.PENDING_DTO, Status.PENDING_POLICE, Status.PENDING_DC)

# From a status (None: not yet submitted) to the statuses it may move to.
_ALLOWED: dict[Status | None, frozenset[Status]] = {
    None: frozenset({Status.PENDING_DTO, Status.ON_HOLD_DUPLICATE_CLAIM}),
    # A duplicate claim is accepted (it goes to the DTO) or rejected.
    Status.ON_HOLD_DUPLICATE_CLAIM: frozenset(
        {Status.PENDING_DTO, Status.REJECTED, Status.EXPIRED}
    ),
    Status.PENDING_DTO: frozenset(
        {Status.PENDING_POLICE, Status.RETURNED_TO_APPLICANT, Status.REJECTED, Status.EXPIRED}
    ),
    Status.PENDING_POLICE: frozenset(
        {
            Status.PENDING_DC,
            Status.RETURNED_TO_APPLICANT,
            Status.REJECTED,
            Status.PENDING_DTO,
            Status.EXPIRED,
        }
    ),
    Status.PENDING_DC: frozenset(
        {
            Status.APPROVED,
            Status.RETURNED_TO_APPLICANT,
            Status.REJECTED,
            Status.PENDING_DTO,
            Status.EXPIRED,
        }
    ),
    # Rejected from here only when a duplicate claim against it is accepted.
    Status.RETURNED_TO_APPLICANT: frozenset({*PENDING_STATUSES, Status.REJECTED, Status.EXPIRED}),
    # A permit expires at the end of its travel date.
    Status.APPROVED: frozenset({Status.EXPIRED}),
}

# What is still open when its travel date passes.
_EXPIRABLE = frozenset(status for status, targets in _ALLOWED.items() if Status.EXPIRED in targets)

STATUS_LABELS: dict[Status, str] = {
    Status.PENDING_DTO: "Pending with DTO",
    Status.ON_HOLD_DUPLICATE_CLAIM: "On hold: duplicate claim",
    Status.PENDING_POLICE: "Pending with Police",
    Status.PENDING_DC: "Pending with DC Office",
    Status.RETURNED_TO_APPLICANT: "Returned to applicant",
    Status.REJECTED: "Rejected",
    Status.APPROVED: "Approved",
    Status.CANCELLED: "Cancelled",
    Status.EXPIRED: "Expired",
}

_OFFICE_OF_STATUS: dict[Status, str] = {
    Status.PENDING_DTO: "the DTO",
    Status.PENDING_POLICE: "the police station",
    Status.PENDING_DC: "the DC office",
}


def office_name(application: Application, status: Status | None = None) -> str | None:
    """The office that holds the application in a pending status, by name."""
    status = status or application.status
    if status in (Status.PENDING_DTO, Status.ON_HOLD_DUPLICATE_CLAIM):
        return application.dto_office.name
    if status == Status.PENDING_POLICE:
        return application.origin_police_station.name
    if status == Status.PENDING_DC:
        return f"DC Office, {application.origin_district.name}"
    return None


def status_url() -> str:
    return f"{get_settings().public_base_url}/status"


def _transition(
    db: Session,
    application: Application,
    new_status: Status,
    *,
    action: str,
    acting: Acting | None = None,
    system_label: str = APPLICANT,
    remarks: str | None = None,
) -> None:
    """Move an application to a new status. Refuses a move the workflow does not allow."""
    old_status = application.status
    if new_status not in _ALLOWED.get(old_status, frozenset()):
        raise DomainError(f"An application cannot move from {old_status or 'new'} to {new_status}.")
    application.status = new_status
    # A new stage starts with the working status "Received".
    application.working_status_id = None
    db.flush()
    new_value: dict[str, object] = {"status": new_status.value}
    if remarks:
        new_value["remarks"] = remarks
    audit.record(
        db,
        actor=acting.user if acting else None,
        officer_name=acting.name if acting else None,
        officer_designation=acting.designation if acting else None,
        system_label=system_label,
        action=action,
        entity_type="application",
        entity_id=application.id,
        entity_label=application.application_number,
        old={"status": old_status.value if old_status else None},
        new=new_value,
    )


def submit(db: Session, application: Application, *, is_duplicate_claim: bool) -> None:
    """A new application arrives: it goes to the DTO, or on hold as a duplicate claim."""
    number = application.application_number

    if is_duplicate_claim:
        _transition(
            db, application, Status.ON_HOLD_DUPLICATE_CLAIM, action="application.submitted_as_claim"
        )
        sms.send(
            db,
            mobile=application.leader_mobile,
            kind=sms.KIND_ON_HOLD,
            application=application,
            message=(
                f"Picnic Portal: application {number} is on hold. Another application exists for "
                "the same vehicle or driver on that date. The DTO will verify your claim. "
                f"This is NOT permission to travel. Status: {status_url()}"
            ),
        )
        return

    _transition(db, application, Status.PENDING_DTO, action="application.submitted")
    sms.send(
        db,
        mobile=application.leader_mobile,
        kind=sms.KIND_SUBMITTED,
        application=application,
        message=(
            f"Picnic Portal: application {number} is submitted and is with the DTO. "
            f"This is NOT permission to travel. Status: {status_url()}"
        ),
    )


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


# Letters and digits that are not mistaken for one another when read aloud or typed.
_CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def _new_verify_code(db: Session) -> str:
    """The random part of the short verification link. It cannot be guessed from the number."""
    while True:
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(10))
        if db.scalar(select(Application.id).where(Application.verify_code == code)) is None:
            return code


def return_to_applicant(
    db: Session, application: Application, *, acting: Acting, remarks: str
) -> None:
    """The office that holds the application sends it back for correction.

    Remarks are mandatory. The office is remembered, so that the corrected
    application comes back to it.
    """
    access.require_holds(acting.user, application)
    remarks = _clean(remarks)
    if not remarks:
        raise DomainError("Enter the remarks for the applicant.")

    office = office_name(application) or "the office"
    application.returned_from_status = application.status
    application.status_remarks = remarks
    _transition(
        db,
        application,
        Status.RETURNED_TO_APPLICANT,
        action="application.returned",
        acting=acting,
        remarks=remarks,
    )
    sms.send(
        db,
        mobile=application.leader_mobile,
        kind=sms.KIND_RETURNED,
        application=application,
        message=(
            f"Picnic Portal: application {application.application_number} is returned by "
            f"{office} for correction. Correct and resubmit it at {status_url()}"
        ),
    )


def resubmit(db: Session, application: Application, *, vehicle_or_driver_changed: bool) -> None:
    """The applicant resubmits a corrected application.

    It goes back to the office that returned it. The one exception: if the
    vehicle or the driver was changed after the DTO stage, it goes back to the
    DTO, the only office that checks them.
    """
    if application.status != Status.RETURNED_TO_APPLICANT:
        raise DomainError("Only a returned application can be resubmitted.")

    target = application.returned_from_status or Status.PENDING_DTO
    rechecked = vehicle_or_driver_changed and target != Status.PENDING_DTO
    if rechecked:
        target = Status.PENDING_DTO

    _transition(db, application, target, action="application.resubmitted")
    application.returned_from_status = None
    application.status_remarks = None

    where = _OFFICE_OF_STATUS[target]
    reason = " because the vehicle or driver was changed" if rechecked else ""
    sms.send(
        db,
        mobile=application.leader_mobile,
        kind=sms.KIND_RESUBMITTED,
        application=application,
        message=(
            f"Picnic Portal: application {application.application_number} is resubmitted and is "
            f"with {where}{reason}. This is NOT permission to travel. Status: {status_url()}"
        ),
    )


# What "forward" means at each stage: the DC office's forward is the final approval.
_NEXT: dict[Status, Status] = {
    Status.PENDING_DTO: Status.PENDING_POLICE,
    Status.PENDING_POLICE: Status.PENDING_DC,
    Status.PENDING_DC: Status.APPROVED,
}


def certificate_confirmed(db: Session, application: Application) -> bool:
    """True when the DTO has confirmed an inspection certificate that still counts.

    It is a certificate of this application, or one already on record for the
    same vehicle. If the vehicle is changed, an earlier confirmation lapses.
    """
    if application.certificate_confirmed_doc_id is None:
        return False
    document = db.get(ApplicationDocument, application.certificate_confirmed_doc_id)
    return (
        document is not None
        and document.doc_type == DocType.INSPECTION_CERTIFICATE
        and document.application.vehicle_reg_key == application.vehicle_reg_key
    )


def forward_blockers(db: Session, application: Application) -> list[str]:
    """What still has to be done before the office that holds the application can forward it.

    An office forwards only when its own tasks are complete. What it found does
    not block by itself: with a "No" or a "Not verified" on record, the office
    still decides whether to forward, return or reject.
    """
    if application.status == Status.PENDING_DTO:
        return _dto_blockers(db, application)
    if application.status == Status.PENDING_POLICE:
        return _police_blockers(application)
    return []


def _dto_blockers(db: Session, application: Application) -> list[str]:
    # Imported here: the DTO service itself uses this module.
    from app.services import dto

    blockers: list[str] = []
    findings = application.dto_findings
    if findings is None:
        blockers.append("Record the VAHAN, challan and SARATHI findings.")
    else:
        unchecked = [
            label
            for group, items in (("vahan", dto.VAHAN_ITEMS), ("sarathi", dto.SARATHI_ITEMS))
            for key, label in items.items()
            if (findings.get(group) or {}).get(key) not in ("YES", "NO")
        ]
        if unchecked:
            blockers.append(
                "Answer Yes or No for every VAHAN and SARATHI item. Not checked: "
                f"{', '.join(unchecked)}."
            )
        if findings.get("challans_unpaid") is None or findings.get("challans_on_record") is None:
            blockers.append("Enter the number of challans unpaid and on record.")

    # The inspection certificate is covered by the inspection itself, below.
    unmarked = [
        document
        for document in application.documents
        if document.verified is None and document.doc_type != DocType.INSPECTION_CERTIFICATE
    ]
    if unmarked:
        blockers.append(
            f"Check {len(unmarked)} document(s) against the originals and mark each "
            "as verified or not verified."
        )

    passed = application.inspection_status == InspectionStatus.PASSED
    if not passed and not certificate_confirmed(db, application):
        blockers.append(
            "Record the vehicle inspection as passed, or accept the inspection certificate "
            "the applicant uploaded."
        )
    return blockers


def _police_blockers(application: Application) -> list[str]:
    findings = application.police_findings or {}
    if (
        application.destination_police_station_id is None
        or not findings.get("driving_time_confirmed")
        or not findings.get("verification_remarks")
    ):
        return [
            "Record the police verification: the destination police station, the driving "
            "time and the verification remarks."
        ]
    return []


def forward(
    db: Session,
    application: Application,
    *,
    acting: Acting,
    remarks: str = "",
    specific_approval_remark: str = "",
) -> None:
    """The DTO forwards to the police station, the police station to the DC office,
    and the DC office approves.
    """
    access.require_holds(acting.user, application)
    blockers = forward_blockers(db, application)
    if blockers:
        raise DomainError("This cannot be forwarded yet. " + " ".join(blockers), errors=blockers)
    target = _NEXT[application.status]
    remarks = _clean(remarks)
    sender = office_name(application) or "the office"
    number = application.application_number

    if target == Status.APPROVED:
        specific = _clean(specific_approval_remark)
        if application.needs_dc_specific_approval and not specific:
            raise DomainError(
                "The driving time is 60 to 90 minutes. Enter the DC's specific approval remark."
            )
        application.dc_specific_approval_remark = specific or None
        if specific:
            remarks = f"{remarks} Specific approval: {specific}".strip()
        _transition(
            db, application, target, action="application.approved", acting=acting, remarks=remarks
        )
        application.status_remarks = None
        # The permit: its number is the application number.
        application.approved_at = now_utc()
        application.approved_by = f"{acting.name}, {acting.designation}"
        application.verify_code = _new_verify_code(db)
        db.flush()
        sms.send(
            db,
            mobile=application.leader_mobile,
            kind=sms.KIND_APPROVED,
            application=application,
            message=(
                f"Picnic Portal: application {number} is APPROVED. Permit number {number}. "
                f"Download the permit with its QR code at {status_url()}, print it and paste "
                "the QR code on the windscreen."
            ),
        )
        return

    _transition(
        db, application, target, action="application.forwarded", acting=acting, remarks=remarks
    )
    sms.send(
        db,
        mobile=application.leader_mobile,
        kind=sms.KIND_FORWARDED,
        application=application,
        message=(
            f"Picnic Portal: application {number} is forwarded by {sender} and is now with "
            f"{office_name(application)}. This is NOT permission to travel. "
            f"Status: {status_url()}"
        ),
    )


def reject(db: Session, application: Application, *, acting: Acting, reason: str) -> None:
    """The office that holds the application closes it. A reason is mandatory."""
    access.require_holds(acting.user, application)
    _reject(db, application, acting=acting, reason=reason, office=office_name(application))


def _reject(
    db: Session, application: Application, *, acting: Acting, reason: str, office: str | None
) -> None:
    reason = _clean(reason)
    if not reason:
        raise DomainError("Enter the reason for rejection.")

    office = office or "the office"
    application.status_remarks = reason
    _transition(
        db,
        application,
        Status.REJECTED,
        action="application.rejected",
        acting=acting,
        remarks=reason,
    )
    sms.send(
        db,
        mobile=application.leader_mobile,
        kind=sms.KIND_REJECTED,
        application=application,
        message=(
            f"Picnic Portal: application {application.application_number} is REJECTED by "
            f"{office}. Reason: {reason}. You may apply afresh."
        ),
    )


# ------------------------------------------------------- duplicate claims


def reject_claim(db: Session, claim: Application, *, acting: Acting, reason: str) -> None:
    """The DTO finds that a duplicate claim is not genuine and closes it."""
    access.require_holds_claim(acting.user, claim)
    _reject(db, claim, acting=acting, reason=reason, office=claim.dto_office.name)


def reject_for_claim(
    db: Session, other: Application, *, claim: Application, acting: Acting, reason: str
) -> None:
    """The DTO accepts a duplicate claim and rejects the application that blocked it.

    The DTO acts as the office that holds the claim. The other application may
    be at any stage before approval, and in any district: the vehicle or the
    driver is the same, wherever the other application was filed.
    """
    access.require_holds_claim(acting.user, claim)
    if other.status == Status.APPROVED:
        raise DomainError(
            f"Application {other.application_number} is already approved. Its permit has to be "
            "cancelled before this claim can be accepted."
        )
    _reject(db, other, acting=acting, reason=reason, office=claim.dto_office.name)


def accept_claim(db: Session, claim: Application, *, acting: Acting, remarks: str = "") -> None:
    """A duplicate claim that nothing blocks any more goes to the DTO as a normal application."""
    access.require_holds_claim(acting.user, claim)
    _transition(
        db,
        claim,
        Status.PENDING_DTO,
        action="application.claim_accepted",
        acting=acting,
        remarks=_clean(remarks),
    )
    sms.send(
        db,
        mobile=claim.leader_mobile,
        kind=sms.KIND_CLAIM_ACCEPTED,
        application=claim,
        message=(
            f"Picnic Portal: your claim for application {claim.application_number} is accepted. "
            f"It is now with {claim.dto_office.name}. This is NOT permission to travel. "
            f"Status: {status_url()}"
        ),
    )


# ---------------------------------------------------------------- transfer


def transfer(
    db: Session,
    application: Application,
    *,
    acting: Acting,
    station: PoliceStation,
    remarks: str,
) -> None:
    """A police station passes an application to the correct station of the same district.

    The status stays "Pending with Police"; the application moves to the other
    station's queue.
    """
    access.require_holds(acting.user, application)
    if application.status != Status.PENDING_POLICE:
        raise DomainError("Only a police station can transfer an application.")
    remarks = _clean(remarks)
    if not remarks:
        raise DomainError("Enter the reason for the transfer.")
    if not station.is_active or station.district_id != application.origin_district_id:
        raise DomainError("Choose an active police station of the same district.")
    if station.id == application.origin_police_station_id:
        raise DomainError("The application is already with this police station.")

    old = application.origin_police_station
    application.origin_police_station = station
    application.working_status_id = None
    db.flush()
    audit.record(
        db,
        actor=acting.user,
        officer_name=acting.name,
        officer_designation=acting.designation,
        action="application.transferred",
        entity_type="application",
        entity_id=application.id,
        entity_label=application.application_number,
        old={"origin_police_station": old.name},
        new={"origin_police_station": station.name, "remarks": remarks},
    )
    sms.send(
        db,
        mobile=application.leader_mobile,
        kind=sms.KIND_TRANSFERRED,
        application=application,
        message=(
            f"Picnic Portal: application {application.application_number} is transferred from "
            f"{old.name} to {station.name} for verification. Status: {status_url()}"
        ),
    )


# ------------------------------------------------------------------ expiry

SYSTEM = "system"


def expire(db: Session, application: Application, *, today: date) -> None:
    """Close an application whose travel date is over.

    A permit expires at the end of its travel date. An application that was
    not approved in time is closed in the same way, so that it leaves the
    work queues.
    """
    if application.travel_date >= today:
        raise DomainError("The travel date of this application is not over.")
    was_permit = application.status == Status.APPROVED
    _transition(db, application, Status.EXPIRED, action="application.expired", system_label=SYSTEM)
    number = application.application_number
    sms.send(
        db,
        mobile=application.leader_mobile,
        kind=sms.KIND_EXPIRED,
        application=application,
        message=(
            f"Picnic Portal: permit {number} has expired, as its travel date is over."
            if was_permit
            else f"Picnic Portal: application {number} was not approved before its travel "
            "date and is now closed. You may apply afresh for another date."
        ),
    )


def expire_due(db: Session, *, today: date) -> int:
    """Expire every open application and permit whose travel date is over. Returns how many."""
    due = db.scalars(
        select(Application)
        .where(Application.travel_date < today, Application.status.in_(_EXPIRABLE))
        .order_by(Application.id)
    )
    count = 0
    for application in due:
        expire(db, application, today=today)
        count += 1
    return count


def send_back_to_dto(db: Session, application: Application, *, acting: Acting, why: str) -> None:
    """After the DTO stage, a changed vehicle, driver or district needs the DTO again.

    Called only from an officer's correction, which has already checked that
    the office holds the application. The check cannot be repeated here: once
    the district is corrected, the application is no longer in that office's
    jurisdiction, which is the very reason it is being moved.
    """
    if application.status == Status.PENDING_DTO:
        return
    _transition(
        db,
        application,
        Status.PENDING_DTO,
        action="application.sent_back_to_dto",
        acting=acting,
        remarks=why,
    )
