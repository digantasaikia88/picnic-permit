"""Duplicate check (PRD Section 10).

A journey is identified by its vehicle and its driver on a travel date:
neither can be on two picnic trips on the same day. A submission is blocked
when an active application exists for the same vehicle registration number,
or the same driving licence number, on the same travel date.
"""

import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Application, Status

# Rejected, cancelled and expired applications do not hold a slot.
INACTIVE_STATUSES = frozenset({Status.REJECTED, Status.CANCELLED, Status.EXPIRED})
ACTIVE_STATUSES = frozenset(Status) - INACTIVE_STATUSES

_SPACES = re.compile(r"\s+")
_SPACES_AND_HYPHENS = re.compile(r"[\s\-]+")


def stored_form(value: str) -> str:
    """How a registration or licence number is stored: no spaces, in capitals."""
    return _SPACES.sub("", value).upper()


def comparison_key(value: str) -> str:
    """How two numbers are compared: no spaces, no hyphens, in capitals."""
    return _SPACES_AND_HYPHENS.sub("", value).upper()


@dataclass(frozen=True)
class Duplicates:
    vehicle: list[Application]
    driver: list[Application]

    def __bool__(self) -> bool:
        return bool(self.vehicle or self.driver)


def find(
    db: Session,
    *,
    vehicle_reg_number: str,
    licence_number: str,
    travel_date: date,
    exclude_application_id: int | None = None,
) -> Duplicates:
    reg_key = comparison_key(vehicle_reg_number)
    licence_key = comparison_key(licence_number)

    statement = select(Application).where(
        Application.travel_date == travel_date,
        Application.status.in_(ACTIVE_STATUSES),
        or_(Application.vehicle_reg_key == reg_key, Application.licence_key == licence_key),
    )
    if exclude_application_id is not None:
        statement = statement.where(Application.id != exclude_application_id)

    matches = list(db.scalars(statement.order_by(Application.id)))
    return Duplicates(
        vehicle=[a for a in matches if a.vehicle_reg_key == reg_key],
        driver=[a for a in matches if a.licence_key == licence_key],
    )
