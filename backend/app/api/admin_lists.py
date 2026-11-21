"""State Admin: working statuses, and the ready reasons for return and rejection."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_state_admin
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.models import Application, RemarkReason, User, WorkingStatus
from app.schemas.officer import (
    FlaggedMobileOut,
    FlaggedMobileUpdate,
    NameUpdate,
    ReasonCreate,
    ReasonOut,
    WorkingStatusCreate,
    WorkingStatusOut,
    WorkingStatusUpdate,
)
from app.services import audit, flags, officer

router = APIRouter(prefix="/admin", tags=["admin: lists"])


def _clean(name: str) -> str:
    name = " ".join(name.split())
    if not name:
        raise DomainError("Enter the text.")
    return name


# --------------------------------------------------------- working statuses


def _working_status(db: Session, row_id: int) -> WorkingStatus:
    row = db.get(WorkingStatus, row_id)
    if row is None:
        raise NotFoundError("Working status not found.")
    return row


def _working_status_free(db: Session, name: str, ignore_id: int | None = None) -> None:
    statement = select(WorkingStatus.id).where(func.lower(WorkingStatus.name) == name.lower())
    if ignore_id is not None:
        statement = statement.where(WorkingStatus.id != ignore_id)
    if db.scalar(statement) is not None or name.lower() == officer.RECEIVED.lower():
        raise ConflictError(f"The working status {name} already exists.")


_OFFICES = ("for_dto", "for_police", "for_dc")


def _working_status_values(row: WorkingStatus) -> dict[str, object]:
    return {
        "name": row.name,
        "is_active": row.is_active,
        **{office: getattr(row, office) for office in _OFFICES},
    }


def _needs_an_office(row: WorkingStatus) -> None:
    if not any(getattr(row, office) for office in _OFFICES):
        raise DomainError("Choose at least one office that uses this working status.")


@router.get("/working-statuses", response_model=list[WorkingStatusOut])
def list_working_statuses(
    db: Session = Depends(get_db), _: User = Depends(require_state_admin)
) -> list[WorkingStatusOut]:
    return officer.working_statuses(db, active_only=False)


@router.post(
    "/working-statuses", response_model=WorkingStatusOut, status_code=status.HTTP_201_CREATED
)
def create_working_status(
    body: WorkingStatusCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> WorkingStatusOut:
    name = _clean(body.name)[:80]
    _working_status_free(db, name)
    row = WorkingStatus(
        name=name, for_dto=body.for_dto, for_police=body.for_police, for_dc=body.for_dc
    )
    _needs_an_office(row)
    db.add(row)
    db.flush()
    audit.record(
        db,
        actor=admin,
        action="working_status.create",
        entity_type="working_status",
        entity_id=row.id,
        entity_label=row.name,
        new={**_working_status_values(row), "is_active": True},
    )
    db.commit()
    return row


@router.patch("/working-statuses/{row_id}", response_model=WorkingStatusOut)
def update_working_status(
    row_id: int,
    body: WorkingStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> WorkingStatusOut:
    row = _working_status(db, row_id)
    before = _working_status_values(row)
    if body.name is not None:
        name = _clean(body.name)[:80]
        _working_status_free(db, name, ignore_id=row.id)
        row.name = name
    if body.is_active is not None:
        row.is_active = body.is_active
    for office in _OFFICES:
        if getattr(body, office) is not None:
            setattr(row, office, getattr(body, office))
    _needs_an_office(row)
    old, new = audit.changed_fields(before, _working_status_values(row))
    if new:
        audit.record(
            db,
            actor=admin,
            action="working_status.update",
            entity_type="working_status",
            entity_id=row.id,
            entity_label=row.name,
            old=old,
            new=new,
        )
    db.commit()
    return row


@router.delete("/working-statuses/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_working_status(
    row_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> None:
    row = _working_status(db, row_id)
    if db.scalar(select(Application.id).where(Application.working_status_id == row.id).limit(1)):
        raise ConflictError(
            "This working status is in use and cannot be deleted. Make it inactive instead."
        )
    audit.record(
        db,
        actor=admin,
        action="working_status.delete",
        entity_type="working_status",
        entity_id=row.id,
        entity_label=row.name,
        old=_working_status_values(row),
    )
    db.delete(row)
    db.commit()


# ------------------------------------------- reasons for return and rejection


def _reason(db: Session, row_id: int) -> RemarkReason:
    row = db.get(RemarkReason, row_id)
    if row is None:
        raise NotFoundError("Reason not found.")
    return row


def _reason_free(db: Session, kind: str, name: str, ignore_id: int | None = None) -> None:
    statement = select(RemarkReason.id).where(
        RemarkReason.kind == kind, func.lower(RemarkReason.name) == name.lower()
    )
    if ignore_id is not None:
        statement = statement.where(RemarkReason.id != ignore_id)
    if db.scalar(statement) is not None:
        raise ConflictError("This reason is already in the list.")


@router.get("/remark-reasons", response_model=list[ReasonOut])
def list_reasons(
    kind: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_state_admin),
) -> list[ReasonOut]:
    statement = select(RemarkReason).order_by(RemarkReason.kind.desc(), RemarkReason.id)
    if kind:
        statement = statement.where(RemarkReason.kind == kind)
    return list(db.scalars(statement))


@router.post("/remark-reasons", response_model=ReasonOut, status_code=status.HTTP_201_CREATED)
def create_reason(
    body: ReasonCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> ReasonOut:
    name = _clean(body.name)
    _reason_free(db, body.kind, name)
    row = RemarkReason(kind=body.kind, name=name)
    db.add(row)
    db.flush()
    audit.record(
        db,
        actor=admin,
        action="remark_reason.create",
        entity_type="remark_reason",
        entity_id=row.id,
        entity_label=row.name,
        new={"kind": row.kind, "name": row.name, "is_active": True},
    )
    db.commit()
    return row


@router.patch("/remark-reasons/{row_id}", response_model=ReasonOut)
def update_reason(
    row_id: int,
    body: NameUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> ReasonOut:
    row = _reason(db, row_id)
    before = {"name": row.name, "is_active": row.is_active}
    if body.name is not None:
        name = _clean(body.name)
        _reason_free(db, row.kind, name, ignore_id=row.id)
        row.name = name
    if body.is_active is not None:
        row.is_active = body.is_active
    old, new = audit.changed_fields(before, {"name": row.name, "is_active": row.is_active})
    if new:
        audit.record(
            db,
            actor=admin,
            action="remark_reason.update",
            entity_type="remark_reason",
            entity_id=row.id,
            entity_label=row.name,
            old=old,
            new=new,
        )
    db.commit()
    return row


@router.delete("/remark-reasons/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reason(
    row_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> None:
    """A reason is copied into the application's remarks when used, so it can be deleted."""
    row = _reason(db, row_id)
    audit.record(
        db,
        actor=admin,
        action="remark_reason.delete",
        entity_type="remark_reason",
        entity_id=row.id,
        entity_label=row.name,
        old={"kind": row.kind, "name": row.name, "is_active": row.is_active},
    )
    db.delete(row)
    db.commit()


# ------------------------------------------------- flagged mobile numbers


@router.get("/flagged-mobiles", response_model=list[FlaggedMobileOut])
def list_flagged_mobiles(
    db: Session = Depends(get_db), _: User = Depends(require_state_admin)
) -> list[FlaggedMobileOut]:
    return flags.list_all(db)


@router.patch("/flagged-mobiles/{row_id}", response_model=FlaggedMobileOut)
def update_flagged_mobile(
    row_id: int,
    body: FlaggedMobileUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> FlaggedMobileOut:
    """Block a flagged number from applying, or lift the block."""
    row = flags.set_blocked(db, admin, row_id, is_blocked=body.is_blocked)
    db.commit()
    return row


@router.delete("/flagged-mobiles/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flagged_mobile(
    row_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> None:
    flags.remove(db, admin, row_id)
    db.commit()
