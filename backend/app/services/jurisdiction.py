"""Who may see what. Every officer has a jurisdiction: the State, a district
or a police station. Later phases call these checks on every request.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.core.errors import PermissionDeniedError
from app.models import Role, User


class Level(StrEnum):
    STATE = "STATE"
    DISTRICT = "DISTRICT"
    POLICE_STATION = "POLICE_STATION"


@dataclass(frozen=True)
class Jurisdiction:
    level: Level
    district_id: int | None = None
    police_station_id: int | None = None

    def covers_district(self, district_id: int) -> bool:
        """True if everything in the district is inside this jurisdiction."""
        if self.level == Level.STATE:
            return True
        return self.level == Level.DISTRICT and self.district_id == district_id

    def covers_police_station(self, police_station_id: int, district_id: int) -> bool:
        """True if the police station (which lies in `district_id`) is inside it."""
        if self.level == Level.POLICE_STATION:
            return self.police_station_id == police_station_id
        return self.covers_district(district_id)


def jurisdiction_of(user: User) -> Jurisdiction:
    if user.role == Role.STATE_ADMIN:
        return Jurisdiction(Level.STATE)

    if user.role == Role.POLICE_STATION:
        if user.police_station is None:
            raise PermissionDeniedError("This account is not linked to a police station.")
        return Jurisdiction(
            Level.POLICE_STATION,
            district_id=user.police_station.district_id,
            police_station_id=user.police_station.id,
        )

    district = user.jurisdiction_district
    if district is not None:
        return Jurisdiction(Level.DISTRICT, district_id=district.id)

    if user.role == Role.VIEWER:
        return Jurisdiction(Level.STATE)

    raise PermissionDeniedError("This account is not linked to an office.")


def require_district(user: User, district_id: int) -> None:
    if not jurisdiction_of(user).covers_district(district_id):
        raise PermissionDeniedError("This is outside your jurisdiction.")


def require_police_station(user: User, police_station_id: int, district_id: int) -> None:
    if not jurisdiction_of(user).covers_police_station(police_station_id, district_id):
        raise PermissionDeniedError("This is outside your jurisdiction.")
