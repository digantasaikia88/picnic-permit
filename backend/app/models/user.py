"""Officer accounts, login sessions and login captchas."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.masters import District, DtoOffice, PoliceStation


class Role(StrEnum):
    STATE_ADMIN = "STATE_ADMIN"
    DTO = "DTO"
    POLICE_STATION = "POLICE_STATION"
    DC_OFFICE = "DC_OFFICE"
    VIEWER = "VIEWER"


class User(Base, TimestampMixin):
    """An officer account.

    The office is linked by internal ID, so the user ID string can be renamed:
      DTO             -> dto_office_id
      POLICE_STATION  -> police_station_id
      DC_OFFICE       -> district_id
      VIEWER          -> district_id, or nothing for a State-level viewer
      STATE_ADMIN     -> nothing
    """

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("user_id = lower(user_id)", name="user_id_lowercase"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True)
    # Empty until a State Admin generates the first password.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, length=20, create_constraint=True, name="role")
    )
    # Only for users whose office is not a master row (viewers and admins).
    office_name: Mapped[str | None] = mapped_column(String(200))

    district_id: Mapped[int | None] = mapped_column(
        ForeignKey("districts.id", ondelete="RESTRICT"), index=True
    )
    police_station_id: Mapped[int | None] = mapped_column(
        ForeignKey("police_stations.id", ondelete="RESTRICT"), index=True
    )
    dto_office_id: Mapped[int | None] = mapped_column(
        ForeignKey("dto_offices.id", ondelete="RESTRICT"), index=True
    )

    must_change_password: Mapped[bool] = mapped_column(server_default=text("true"))
    failed_attempts: Mapped[int] = mapped_column(server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    district: Mapped[District | None] = relationship()
    police_station: Mapped[PoliceStation | None] = relationship()
    dto_office: Mapped[DtoOffice | None] = relationship()

    @property
    def office_label(self) -> str:
        """The office name to show, taken from the master row where there is one."""
        if self.role == Role.DTO and self.dto_office:
            return self.dto_office.name
        if self.role == Role.POLICE_STATION and self.police_station:
            return self.police_station.name
        if self.role == Role.DC_OFFICE and self.district:
            return f"DC Office, {self.district.name}"
        if self.office_name:
            return self.office_name
        if self.role == Role.STATE_ADMIN:
            return "State User Management Admin"
        if self.role == Role.VIEWER and self.district:
            return f"Viewer, {self.district.name}"
        return "State viewer"

    @property
    def jurisdiction_district(self) -> District | None:
        """The district this user belongs to, or None for State-level users."""
        if self.role == Role.DTO and self.dto_office:
            return self.dto_office.district
        if self.role == Role.POLICE_STATION and self.police_station:
            return self.police_station.district
        return self.district


class UserSession(Base):
    """A login session. Only a hash of the cookie token is stored."""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


class Captcha(Base):
    """A captcha challenge waiting to be answered. Deleted on the first attempt."""

    __tablename__ = "captchas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    answer_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
