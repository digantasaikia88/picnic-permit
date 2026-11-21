"""Mobile numbers that filed a fake or prank application (PRD Section 10.1).

A flagged number shows a warning to officers on its applications. A State
Admin can block a flagged number from applying.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError, NotFoundError
from app.models import Application, FlaggedMobile, User
from app.services import audit
from app.services.access import Acting

BLOCKED_MESSAGE = (
    "This mobile number cannot be used to apply on the portal. Please contact the DTO office."
)


def get(db: Session, mobile: str) -> FlaggedMobile | None:
    return db.scalar(select(FlaggedMobile).where(FlaggedMobile.mobile == mobile))


def refuse_if_blocked(db: Session, mobile: str) -> None:
    found = get(db, mobile)
    if found is not None and found.is_blocked:
        raise DomainError(BLOCKED_MESSAGE)


def flag(db: Session, application: Application, *, acting: Acting, reason: str) -> FlaggedMobile:
    """Flag the mobile number that filed this application. Flagging twice changes nothing."""
    found = get(db, application.leader_mobile)
    if found is not None:
        return found
    row = FlaggedMobile(
        mobile=application.leader_mobile,
        reason=reason,
        application_number=application.application_number,
        flagged_by=f"{acting.name}, {acting.designation} ({acting.user.office_label})",
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        actor=acting.user,
        officer_name=acting.name,
        officer_designation=acting.designation,
        action="flagged_mobile.create",
        entity_type="flagged_mobile",
        entity_id=row.id,
        entity_label=row.mobile,
        new={
            "mobile": row.mobile,
            "reason": reason,
            "application_number": application.application_number,
        },
    )
    return row


def list_all(db: Session) -> list[FlaggedMobile]:
    return list(db.scalars(select(FlaggedMobile).order_by(FlaggedMobile.id.desc())))


def _row(db: Session, row_id: int) -> FlaggedMobile:
    row = db.get(FlaggedMobile, row_id)
    if row is None:
        raise NotFoundError("Flagged mobile number not found.")
    return row


def set_blocked(db: Session, admin: User, row_id: int, *, is_blocked: bool) -> FlaggedMobile:
    row = _row(db, row_id)
    if row.is_blocked != is_blocked:
        row.is_blocked = is_blocked
        audit.record(
            db,
            actor=admin,
            action="flagged_mobile.update",
            entity_type="flagged_mobile",
            entity_id=row.id,
            entity_label=row.mobile,
            old={"is_blocked": not is_blocked},
            new={"is_blocked": is_blocked},
        )
    return row


def remove(db: Session, admin: User, row_id: int) -> None:
    """Take the flag off a number, for example one flagged by mistake."""
    row = _row(db, row_id)
    audit.record(
        db,
        actor=admin,
        action="flagged_mobile.delete",
        entity_type="flagged_mobile",
        entity_id=row.id,
        entity_label=row.mobile,
        old={"mobile": row.mobile, "reason": row.reason, "is_blocked": row.is_blocked},
    )
    db.delete(row)


def flagged_among(db: Session, mobiles: set[str]) -> set[str]:
    """Which of these mobile numbers are flagged."""
    if not mobiles:
        return set()
    return set(db.scalars(select(FlaggedMobile.mobile).where(FlaggedMobile.mobile.in_(mobiles))))
