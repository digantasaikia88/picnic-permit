"""Duplicate claims (PRD Section 10.1).

An applicant blocked by the duplicate check may raise a claim. The claim waits
"on hold" with the DTO of its district. The DTO compares it with the
application that blocks it and decides which one is genuine.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import Application, ApplicationDocument, Status, User
from app.services import access, duplicates, flags, workflow
from app.services.access import Acting

UNAUTHORISED = "Not authorised by the vehicle owner or driver"


@dataclass(frozen=True)
class Blocking:
    application: Application
    same_vehicle: bool
    same_driver: bool


def waiting(db: Session, user: User) -> list[Application]:
    """The duplicate claims waiting for this DTO office, earliest travel date first."""
    if user.dto_office is None:
        return []
    return list(
        db.scalars(
            select(Application)
            .where(
                Application.status == Status.ON_HOLD_DUPLICATE_CLAIM,
                Application.dto_office_id == user.dto_office.id,
            )
            .order_by(Application.travel_date, Application.id)
        )
    )


def get(db: Session, user: User, application_id: int) -> Application:
    claim = db.get(Application, application_id)
    if claim is None or not access.holds_claim(user, claim):
        raise NotFoundError("Duplicate claim not found.")
    return claim


def blocking(db: Session, claim: Application) -> list[Blocking]:
    """The active applications with the same vehicle or driver on the same date.

    They may belong to any district: the vehicle or the driver is the same,
    wherever the other application was filed.
    """
    found = duplicates.find(
        db,
        vehicle_reg_number=claim.vehicle_reg_number,
        licence_number=claim.licence_number,
        travel_date=claim.travel_date,
        exclude_application_id=claim.id,
    )
    vehicle_ids = {a.id for a in found.vehicle}
    driver_ids = {a.id for a in found.driver}
    others = {a.id: a for a in [*found.vehicle, *found.driver]}
    return [
        Blocking(
            application=other,
            same_vehicle=other.id in vehicle_ids,
            same_driver=other.id in driver_ids,
        )
        for _id, other in sorted(others.items())
    ]


def other_document(
    db: Session, claim: Application, other_id: int, document_id: int
) -> ApplicationDocument:
    """A document of an application that blocks this claim, for the side-by-side check."""
    for item in blocking(db, claim):
        if item.application.id == other_id:
            for document in item.application.documents:
                if document.id == document_id:
                    return document
    raise NotFoundError("Document not found.")


def accept(
    db: Session, claim: Application, *, acting: Acting, remarks: str, flag_mobiles: bool
) -> None:
    """The claim is genuine: reject what blocks it, and send the claim to the DTO's queue.

    If nothing blocks the claim any more (the other application was rejected
    or cancelled meanwhile), the claim simply moves on.
    """
    access.require_holds_claim(acting.user, claim)
    remarks = " ".join(remarks.split())
    reason = f"{UNAUTHORISED}. {remarks}" if remarks else UNAUTHORISED
    for item in blocking(db, claim):
        other = item.application
        workflow.reject_for_claim(db, other, claim=claim, acting=acting, reason=reason)
        if flag_mobiles:
            flags.flag(
                db,
                other,
                acting=acting,
                reason=f"Duplicate claim {claim.application_number} accepted. {reason}",
            )
    workflow.accept_claim(db, claim, acting=acting, remarks=remarks)


def reject(
    db: Session, claim: Application, *, acting: Acting, reason: str, flag_mobile: bool
) -> None:
    """The claim is not genuine: close it. The other application carries on."""
    workflow.reject_claim(db, claim, acting=acting, reason=reason)
    if flag_mobile:
        flags.flag(db, claim, acting=acting, reason=f"Duplicate claim rejected. {reason}")
