"""Master data: districts, police stations and DTO offices.

Rows are referred to by the internal `id`, never by name or code, so a
district or station can be renamed or moved without breaking records.
"""

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class District(Base, TimestampMixin):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The "District ID" of the district master, for example 1022 for Tinsukia.
    code: Mapped[int] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    # Used to build user IDs: dto.<short_name>, dc.<short_name>. Editable by the admin.
    short_name: Mapped[str] = mapped_column(String(30), unique=True)
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))

    police_stations: Mapped[list[PoliceStation]] = relationship(back_populates="district")
    dto_offices: Mapped[list[DtoOffice]] = relationship(back_populates="district")


class PoliceStation(Base, TimestampMixin):
    __tablename__ = "police_stations"
    __table_args__ = (UniqueConstraint("district_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    district_id: Mapped[int] = mapped_column(
        ForeignKey("districts.id", ondelete="RESTRICT"), index=True
    )
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))

    district: Mapped[District] = relationship(back_populates="police_stations")


class DtoOffice(Base, TimestampMixin):
    __tablename__ = "dto_offices"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The "DTO Office ID" of the DTO office master, for example DTO-1022.
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    district_id: Mapped[int] = mapped_column(
        ForeignKey("districts.id", ondelete="RESTRICT"), index=True
    )
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))

    district: Mapped[District] = relationship(back_populates="dto_offices")
