from pydantic import BaseModel, Field

from app.models import Role, User
from app.services.jurisdiction import Level, jurisdiction_of


class CaptchaResponse(BaseModel):
    enabled: bool
    captcha_id: str | None = None
    # PNG image as a data URL.
    image: str | None = None


class LoginRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    captcha_id: str | None = Field(default=None, max_length=36)
    captcha_answer: str | None = Field(default=None, max_length=16)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class MeResponse(BaseModel):
    id: int
    user_id: str
    role: Role
    office: str
    must_change_password: bool
    jurisdiction_level: Level
    district_id: int | None
    district_name: str | None
    police_station_id: int | None
    police_station_name: str | None

    @classmethod
    def from_user(cls, user: User) -> MeResponse:
        jurisdiction = jurisdiction_of(user)
        district = user.jurisdiction_district
        return cls(
            id=user.id,
            user_id=user.user_id,
            role=user.role,
            office=user.office_label,
            must_change_password=user.must_change_password,
            jurisdiction_level=jurisdiction.level,
            district_id=district.id if district else None,
            district_name=district.name if district else None,
            police_station_id=user.police_station.id if user.police_station else None,
            police_station_name=user.police_station.name if user.police_station else None,
        )
