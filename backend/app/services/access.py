"""Which officer may see or act on which application.

Authorisation is decided here, in the backend, on every request. An office
acts only on an application that is pending at its own stage and inside its
jurisdiction. It may look at more than it may act on.
"""

from dataclasses import dataclass

from sqlalchemy import ColumnElement, false, or_

from app.core.errors import DomainError, NotFoundError, PermissionDeniedError
from app.models import Application, Role, Status, User

# The stage at which each office works.
STAGE_OF_ROLE: dict[Role, Status] = {
    Role.DTO: Status.PENDING_DTO,
    Role.POLICE_STATION: Status.PENDING_POLICE,
    Role.DC_OFFICE: Status.PENDING_DC,
}
WORKFLOW_ROLES = tuple(STAGE_OF_ROLE)


@dataclass(frozen=True)
class Acting:
    """The logged-in office user and the officer who is taking the action.

    An office may share one user ID, so every action carries the name and
    designation of the person who took it.
    """

    user: User
    name: str
    designation: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.designation.strip():
            raise DomainError("Enter your name and designation.")


def _in_jurisdiction(user: User, application: Application) -> bool:
    if user.role == Role.DTO:
        office = user.dto_office
        return office is not None and (
            application.dto_office_id == office.id
            or application.origin_district_id == office.district_id
        )
    if user.role == Role.POLICE_STATION:
        return (
            user.police_station_id is not None
            and application.origin_police_station_id == user.police_station_id
        )
    if user.role == Role.DC_OFFICE:
        return user.district_id is not None and application.origin_district_id == user.district_id
    return False


def visible_filter(user: User) -> ColumnElement[bool]:
    """SQL condition for the applications an office may look at."""
    if user.role == Role.DTO and user.dto_office is not None:
        return or_(
            Application.dto_office_id == user.dto_office.id,
            Application.origin_district_id == user.dto_office.district_id,
        )
    if user.role == Role.POLICE_STATION and user.police_station_id is not None:
        return Application.origin_police_station_id == user.police_station_id
    if user.role == Role.DC_OFFICE and user.district_id is not None:
        return Application.origin_district_id == user.district_id
    return false()


def queue_filter(user: User) -> ColumnElement[bool]:
    """SQL condition for the applications waiting for this office to act."""
    stage = STAGE_OF_ROLE.get(user.role)
    if stage is None:
        return false()
    if user.role == Role.DTO and user.dto_office is not None:
        # The queue is the office's own; the wider district is for looking only.
        return (Application.status == stage) & (Application.dto_office_id == user.dto_office.id)
    return (Application.status == stage) & visible_filter(user)


def can_view(user: User, application: Application) -> bool:
    return user.role in STAGE_OF_ROLE and _in_jurisdiction(user, application)


def holds(user: User, application: Application) -> bool:
    """True when the application is pending with this user's office."""
    if STAGE_OF_ROLE.get(user.role) != application.status:
        return False
    if user.role == Role.DTO:
        return user.dto_office is not None and application.dto_office_id == user.dto_office.id
    return _in_jurisdiction(user, application)


def holds_claim(user: User, application: Application) -> bool:
    """True when the application is a duplicate claim waiting for this DTO office."""
    return (
        user.role == Role.DTO
        and user.dto_office is not None
        and application.status == Status.ON_HOLD_DUPLICATE_CLAIM
        and application.dto_office_id == user.dto_office.id
    )


def require_holds_claim(user: User, application: Application) -> None:
    if not holds_claim(user, application):
        raise PermissionDeniedError("This duplicate claim is not pending with your office.")


def require_view(user: User, application: Application | None) -> Application:
    """An application outside the jurisdiction answers like one that does not exist."""
    if application is None or not can_view(user, application):
        raise NotFoundError("Application not found.")
    return application


def require_holds(user: User, application: Application) -> None:
    if not can_view(user, application):
        raise NotFoundError("Application not found.")
    if not holds(user, application):
        raise PermissionDeniedError("This application is not pending with your office.")
