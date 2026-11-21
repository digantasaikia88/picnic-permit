"""User ID naming rules (PRD Section 3.2).

    DTO              dto.<district short name>            dto.tinsukia
    DC office        dc.<district short name>             dc.salmara
    Police station   ps.<station name, no spaces or PS>   ps.margherita
      name clash     ps.<station>.<district short name>   ps.lakhipur.cachar
    Second user      <first user ID>.<number>             dto.tinsukia.2
    State admin      admin.<number>                       admin.1
    SP office viewer sp.<district short name>             sp.tinsukia
    State viewer     transport.state.<number>             transport.state.1

Lowercase letters, digits and dots only. Login is not case-sensitive.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models import District, DtoOffice, PoliceStation, Role, User

_USER_ID_RE = re.compile(r"^[a-z0-9]+(\.[a-z0-9]+)*$")
_SHORT_NAME_RE = re.compile(r"^[a-z0-9]+$")
_TRAILING_PS_RE = re.compile(r"\s+PS$", re.IGNORECASE)
_NOT_ALNUM_RE = re.compile(r"[^a-z0-9]")


def normalise_user_id(user_id: str) -> str:
    return user_id.strip().lower()


def is_valid_user_id(user_id: str) -> bool:
    return len(user_id) <= 64 and bool(_USER_ID_RE.fullmatch(user_id))


def is_valid_short_name(short_name: str) -> bool:
    return len(short_name) <= 30 and bool(_SHORT_NAME_RE.fullmatch(short_name))


def station_slug(name: str) -> str:
    """'Barpeta Road PS' -> 'barpetaroad', 'R.K. Nagar PS' -> 'rknagar'."""
    without_ps = _TRAILING_PS_RE.sub("", name.strip())
    return _NOT_ALNUM_RE.sub("", without_ps.lower())


def _owner(db: Session, user_id: str) -> User | None:
    return db.scalar(select(User).where(User.user_id == user_id))


def _first_free(db: Session, base: str) -> str:
    """`base`, or `base.2`, `base.3`, ... for further users of the same office."""
    if _owner(db, base) is None:
        return base
    number = 2
    while _owner(db, f"{base}.{number}") is not None:
        number += 1
    return f"{base}.{number}"


def _first_free_numbered(db: Session, stem: str) -> str:
    """`stem.1`, `stem.2`, ... for users that are always numbered."""
    number = 1
    while _owner(db, f"{stem}.{number}") is not None:
        number += 1
    return f"{stem}.{number}"


def _station_base(db: Session, station: PoliceStation) -> str:
    slug = station_slug(station.name)
    if not slug:
        raise DomainError("A user ID cannot be built from this police station name.")
    base = f"ps.{slug}"

    # A clash: the plain ID belongs to another station, or an older station
    # with the same name exists. Then the district short name is added.
    owner = _owner(db, base)
    owned_by_other = owner is not None and owner.police_station_id != station.id
    older_same_name = any(
        other.id < station.id and station_slug(other.name) == slug
        for other in db.scalars(select(PoliceStation).where(PoliceStation.id != station.id))
    )
    if owned_by_other or older_same_name:
        return f"{base}.{station.district.short_name}"
    return base


def suggest_user_id(
    db: Session,
    role: Role,
    *,
    district: District | None = None,
    police_station: PoliceStation | None = None,
    dto_office: DtoOffice | None = None,
) -> str:
    """The next free user ID for a new user of this office."""
    if role == Role.STATE_ADMIN:
        return _first_free_numbered(db, "admin")
    if role == Role.DTO:
        if dto_office is None:
            raise DomainError("Choose the DTO office.")
        return _first_free(db, f"dto.{dto_office.district.short_name}")
    if role == Role.DC_OFFICE:
        if district is None:
            raise DomainError("Choose the district.")
        return _first_free(db, f"dc.{district.short_name}")
    if role == Role.POLICE_STATION:
        if police_station is None:
            raise DomainError("Choose the police station.")
        return _first_free(db, _station_base(db, police_station))
    if district is not None:
        return _first_free(db, f"sp.{district.short_name}")
    return _first_free_numbered(db, "transport.state")
