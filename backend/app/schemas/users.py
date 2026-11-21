from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models import AuditLog, Role, User
from app.services import users as user_service


class UserOut(BaseModel):
    id: int
    user_id: str
    role: Role
    office: str
    district_id: int | None
    district_name: str | None
    police_station_id: int | None
    dto_office_id: int | None
    # ACTIVE, INACTIVE, LOCKED, NO_PASSWORD or MUST_CHANGE_PASSWORD
    status: str
    is_active: bool
    last_login_at: datetime | None

    @classmethod
    def from_user(cls, user: User) -> UserOut:
        district = user.jurisdiction_district
        return cls(
            id=user.id,
            user_id=user.user_id,
            role=user.role,
            office=user.office_label,
            district_id=district.id if district else None,
            district_name=district.name if district else None,
            police_station_id=user.police_station_id,
            dto_office_id=user.dto_office_id,
            status=user_service.status_of(user),
            is_active=user.is_active,
            last_login_at=user.last_login_at,
        )


class UserList(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


class UserCreate(BaseModel):
    role: Role
    district_id: int | None = None
    police_station_id: int | None = None
    dto_office_id: int | None = None
    # Leave empty to use the generated user ID.
    user_id: str | None = Field(default=None, max_length=64)
    office_name: str | None = Field(default=None, max_length=200)


class UserUpdate(BaseModel):
    user_id: str | None = Field(default=None, min_length=1, max_length=64)
    is_active: bool | None = None
    office_name: str | None = Field(default=None, max_length=200)


class UserWithPassword(BaseModel):
    """Returned once, when a password is generated. It cannot be shown again."""

    user: UserOut
    password: str


class SuggestedUserId(BaseModel):
    user_id: str


class PendingPasswords(BaseModel):
    never_issued: int
    issued_never_logged_in: int


class SettingOut(BaseModel):
    key: str
    value: int
    description: str
    min_value: int
    max_value: int

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    value: int


class AuditOut(BaseModel):
    id: int
    at: datetime
    actor: str
    action: str
    entity_type: str
    entity_label: str | None
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None

    @classmethod
    def from_row(cls, row: AuditLog) -> AuditOut:
        return cls(
            id=row.id,
            at=row.at,
            actor=row.actor_label,
            action=row.action,
            entity_type=row.entity_type,
            entity_label=row.entity_label,
            old_value=row.old_value,
            new_value=row.new_value,
        )


class AuditList(BaseModel):
    items: list[AuditOut]
    total: int
    page: int
    page_size: int
