"""What an office sees and does besides moving an application: queues, the
district view, alerts, the timeline and the working status.
"""

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError, NotFoundError
from app.models import Application, AuditLog, RemarkReason, Role, Status, User, WorkingStatus
from app.services import access, audit, duplicates
from app.services.access import Acting

RECEIVED = "Received"
REASON_KINDS = ("RETURN", "REJECT")


def working_status_label(application: Application) -> str | None:
    """Shown to the applicant and in the queues while an office holds the application."""
    if application.status not in access.STAGE_OF_ROLE.values():
        return None
    return application.working_status.name if application.working_status else RECEIVED


# ------------------------------------------------------------------ lists


def _search_filter(search: str):
    """Application number, vehicle number or mobile number."""
    text = search.strip()
    key = duplicates.comparison_key(text)
    digits = "".join(ch for ch in text if ch.isdigit())
    conditions = [Application.vehicle_reg_key.contains(key, autoescape=True)] if key else []
    if digits:
        conditions.append(Application.application_number.contains(digits))
        conditions.append(Application.leader_mobile.contains(digits))
    return or_(*conditions) if conditions else None


def queue(db: Session, user: User, *, search: str | None = None) -> list[Application]:
    """Applications waiting for this office, earliest travel date first."""
    statement = select(Application).where(access.queue_filter(user))
    condition = _search_filter(search) if search else None
    if condition is not None:
        statement = statement.where(condition)
    return list(db.scalars(statement.order_by(Application.travel_date, Application.id)))


def visible(
    db: Session,
    user: User,
    *,
    status: Status | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Application], int]:
    """Every application the office may look at, newest first."""
    statement = select(Application).where(access.visible_filter(user))
    if status is not None:
        statement = statement.where(Application.status == status)
    condition = _search_filter(search) if search else None
    if condition is not None:
        statement = statement.where(condition)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(
        statement.order_by(Application.submitted_at.desc(), Application.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total


def get_for(db: Session, user: User, application_id: int) -> Application:
    return access.require_view(user, db.get(Application, application_id))


# ----------------------------------------------------------------- alerts


@dataclass(frozen=True)
class Alert:
    application_number: str
    travel_date: str
    status: Status
    district: str
    same_vehicle: bool
    same_driver: bool
    same_leader: bool
    # Set when that application was rejected.
    rejection_reason: str | None


def alerts(db: Session, application: Application) -> list[Alert]:
    """Other applications with the same vehicle, driver or group leader's mobile.

    They are shown whatever district they belong to, with only what an officer
    needs to judge: number, date, status and district.
    """
    others = db.scalars(
        select(Application)
        .where(
            Application.id != application.id,
            or_(
                Application.vehicle_reg_key == application.vehicle_reg_key,
                Application.licence_key == application.licence_key,
                Application.leader_mobile == application.leader_mobile,
            ),
        )
        .order_by(Application.travel_date.desc(), Application.id.desc())
        .limit(50)
    )
    return [
        Alert(
            application_number=other.application_number,
            travel_date=other.travel_date.isoformat(),
            status=other.status,
            district=other.origin_district.name,
            same_vehicle=other.vehicle_reg_key == application.vehicle_reg_key,
            same_driver=other.licence_key == application.licence_key,
            same_leader=other.leader_mobile == application.leader_mobile,
            rejection_reason=other.status_remarks if other.status == Status.REJECTED else None,
        )
        for other in others
    ]


# --------------------------------------------------------------- timeline


def timeline(db: Session, application: Application) -> list[AuditLog]:
    """Who did what and when, oldest first."""
    return list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.entity_type == "application", AuditLog.entity_id == str(application.id))
            .order_by(AuditLog.id)
        )
    )


# --------------------------------------------------------- working status


def set_working_status(
    db: Session, application: Application, *, acting: Acting, working_status_id: int | None
) -> None:
    """The office that holds the application says what it is doing with it."""
    access.require_holds(acting.user, application)
    new: WorkingStatus | None = None
    if working_status_id is not None:
        new = db.get(WorkingStatus, working_status_id)
        if new is None or not new.is_active or not offered_to(new, acting.user.role):
            raise DomainError("Choose a working status from the list.")

    old_label = working_status_label(application)
    application.working_status = new
    db.flush()
    new_label = working_status_label(application)
    if old_label == new_label:
        return
    audit.record(
        db,
        actor=acting.user,
        officer_name=acting.name,
        officer_designation=acting.designation,
        action="application.working_status",
        entity_type="application",
        entity_id=application.id,
        entity_label=application.application_number,
        old={"working_status": old_label},
        new={"working_status": new_label},
    )


# ---------------------------------------------------------- ready remarks


def reasons(db: Session, kind: str, *, active_only: bool = True) -> list[RemarkReason]:
    statement = select(RemarkReason).where(RemarkReason.kind == kind).order_by(RemarkReason.id)
    if active_only:
        statement = statement.where(RemarkReason.is_active)
    return list(db.scalars(statement))


# The column that says whether a working status is offered to an office.
_OFFERED_TO = {
    Role.DTO: WorkingStatus.for_dto,
    Role.POLICE_STATION: WorkingStatus.for_police,
    Role.DC_OFFICE: WorkingStatus.for_dc,
}


def offered_to(working_status: WorkingStatus, role: Role) -> bool:
    column = _OFFERED_TO.get(role)
    return column is not None and bool(getattr(working_status, column.key))


def working_statuses(
    db: Session, *, active_only: bool = True, role: Role | None = None
) -> list[WorkingStatus]:
    """The working statuses, or only those offered to the office of the given role."""
    statement = select(WorkingStatus).order_by(WorkingStatus.id)
    if active_only:
        statement = statement.where(WorkingStatus.is_active)
    if role is not None:
        statement = statement.where(_OFFERED_TO[role])
    return list(db.scalars(statement))


def compose_remarks(db: Session, kind: str, reason_id: int | None, remarks: str) -> str:
    """A reason from the list, a free-text remark, or both joined."""
    remarks = " ".join(remarks.split())
    if reason_id is None:
        return remarks
    reason = db.get(RemarkReason, reason_id)
    if reason is None or reason.kind != kind or not reason.is_active:
        raise NotFoundError("Choose a reason from the list.")
    return f"{reason.name}. {remarks}" if remarks else reason.name
