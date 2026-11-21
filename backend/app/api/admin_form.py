"""State Admin: vehicle types and the picnic season."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_state_admin
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.models import Application, EmergencyContact, User, VehicleType
from app.schemas.application import (
    EmergencyContactCreate,
    EmergencyContactOut,
    EmergencyContactUpdate,
    SeasonIn,
    SeasonOut,
    VehicleTypeCreate,
    VehicleTypeOut,
    VehicleTypeUpdate,
)
from app.services import audit, masters, validation

router = APIRouter(prefix="/admin", tags=["admin: form"])


def _get_type(db: Session, type_id: int) -> VehicleType:
    row = db.get(VehicleType, type_id)
    if row is None:
        raise NotFoundError("Vehicle type not found.")
    return row


def _clean_type_name(db: Session, name: str, ignore_id: int | None = None) -> str:
    name = " ".join(name.split())
    if not name:
        raise DomainError("Enter the vehicle type.")
    statement = select(VehicleType.id).where(func.lower(VehicleType.name) == name.lower())
    if ignore_id is not None:
        statement = statement.where(VehicleType.id != ignore_id)
    if db.scalar(statement) is not None:
        raise ConflictError(f"The vehicle type {name} already exists.")
    return name


@router.get("/vehicle-types", response_model=list[VehicleTypeOut])
def list_vehicle_types(
    db: Session = Depends(get_db), _: User = Depends(require_state_admin)
) -> list[VehicleTypeOut]:
    return list(db.scalars(select(VehicleType).order_by(VehicleType.id)))


@router.post("/vehicle-types", response_model=VehicleTypeOut, status_code=status.HTTP_201_CREATED)
def create_vehicle_type(
    body: VehicleTypeCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> VehicleTypeOut:
    row = VehicleType(name=_clean_type_name(db, body.name))
    db.add(row)
    db.flush()
    audit.record(
        db,
        actor=admin,
        action="vehicle_type.create",
        entity_type="vehicle_type",
        entity_id=row.id,
        entity_label=row.name,
        new={"name": row.name, "is_active": True},
    )
    db.commit()
    return row


@router.patch("/vehicle-types/{type_id}", response_model=VehicleTypeOut)
def update_vehicle_type(
    type_id: int,
    body: VehicleTypeUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> VehicleTypeOut:
    row = _get_type(db, type_id)
    before = {"name": row.name, "is_active": row.is_active}
    if body.name is not None:
        row.name = _clean_type_name(db, body.name, ignore_id=row.id)
    if body.is_active is not None:
        row.is_active = body.is_active
    old, new = audit.changed_fields(before, {"name": row.name, "is_active": row.is_active})
    if new:
        audit.record(
            db,
            actor=admin,
            action="vehicle_type.update",
            entity_type="vehicle_type",
            entity_id=row.id,
            entity_label=row.name,
            old=old,
            new=new,
        )
    db.commit()
    return row


@router.delete("/vehicle-types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle_type(
    type_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> None:
    row = _get_type(db, type_id)
    if db.scalar(select(Application.id).where(Application.vehicle_type_id == row.id).limit(1)):
        raise ConflictError(
            "This vehicle type is in use and cannot be deleted. Make it inactive instead."
        )
    audit.record(
        db,
        actor=admin,
        action="vehicle_type.delete",
        entity_type="vehicle_type",
        entity_id=row.id,
        entity_label=row.name,
        old={"name": row.name, "is_active": row.is_active},
    )
    db.delete(row)
    db.commit()


@router.get("/season", response_model=SeasonOut)
def get_season(db: Session = Depends(get_db), _: User = Depends(require_state_admin)) -> SeasonOut:
    season = validation.get_season(db)
    db.commit()
    return season


@router.put("/season", response_model=SeasonOut)
def set_season(
    body: SeasonIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> SeasonOut:
    """Set both dates, or clear both to remove the season limit."""
    if (body.start_date is None) != (body.end_date is None):
        raise DomainError("Enter both the start date and the end date, or clear both.")
    if body.start_date and body.end_date and body.end_date < body.start_date:
        raise DomainError("The end date cannot be earlier than the start date.")

    season = validation.get_season(db)
    before = {
        "start_date": season.start_date.isoformat() if season.start_date else None,
        "end_date": season.end_date.isoformat() if season.end_date else None,
    }
    season.start_date, season.end_date = body.start_date, body.end_date
    after = {
        "start_date": body.start_date.isoformat() if body.start_date else None,
        "end_date": body.end_date.isoformat() if body.end_date else None,
    }
    old, new = audit.changed_fields(before, after)
    if new:
        audit.record(
            db,
            actor=admin,
            action="season.update",
            entity_type="setting",
            entity_id="picnic_season",
            entity_label="Picnic season",
            old=old,
            new=new,
        )
    db.commit()
    return season


# ------------------------------------------------------ emergency contacts


def _contact_dict(row: EmergencyContact) -> dict[str, object]:
    return {
        "district_id": row.district_id,
        "name": row.name,
        "phone": row.phone,
        "is_active": row.is_active,
    }


def _get_contact(db: Session, contact_id: int) -> EmergencyContact:
    row = db.get(EmergencyContact, contact_id)
    if row is None:
        raise NotFoundError("Emergency contact not found.")
    return row


@router.get("/emergency-contacts", response_model=list[EmergencyContactOut])
def list_emergency_contacts(
    district_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_state_admin),
) -> list[EmergencyContactOut]:
    statement = select(EmergencyContact).order_by(EmergencyContact.district_id, EmergencyContact.id)
    if district_id is not None:
        statement = statement.where(EmergencyContact.district_id == district_id)
    return list(db.scalars(statement))


@router.post(
    "/emergency-contacts",
    response_model=EmergencyContactOut,
    status_code=status.HTTP_201_CREATED,
)
def create_emergency_contact(
    body: EmergencyContactCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> EmergencyContactOut:
    district = masters.get_district(db, body.district_id)
    row = EmergencyContact(
        district_id=district.id, name=" ".join(body.name.split()), phone=body.phone
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        actor=admin,
        action="emergency_contact.create",
        entity_type="emergency_contact",
        entity_id=row.id,
        entity_label=f"{row.name}, {district.name}",
        new=_contact_dict(row),
    )
    db.commit()
    return row


@router.patch("/emergency-contacts/{contact_id}", response_model=EmergencyContactOut)
def update_emergency_contact(
    contact_id: int,
    body: EmergencyContactUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> EmergencyContactOut:
    row = _get_contact(db, contact_id)
    before = _contact_dict(row)
    if body.district_id is not None:
        row.district_id = masters.get_district(db, body.district_id).id
    if body.name is not None:
        row.name = " ".join(body.name.split())
    if body.phone is not None:
        row.phone = body.phone
    if body.is_active is not None:
        row.is_active = body.is_active
    old, new = audit.changed_fields(before, _contact_dict(row))
    if new:
        audit.record(
            db,
            actor=admin,
            action="emergency_contact.update",
            entity_type="emergency_contact",
            entity_id=row.id,
            entity_label=row.name,
            old=old,
            new=new,
        )
    db.commit()
    return row


@router.delete("/emergency-contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_emergency_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> None:
    row = _get_contact(db, contact_id)
    audit.record(
        db,
        actor=admin,
        action="emergency_contact.delete",
        entity_type="emergency_contact",
        entity_id=row.id,
        entity_label=row.name,
        old=_contact_dict(row),
    )
    db.delete(row)
    db.commit()
