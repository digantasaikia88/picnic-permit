from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AppSetting(Base, TimestampMixin):
    """A whole-number setting the admin can change without a code change."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(300))
    min_value: Mapped[int] = mapped_column(Integer)
    max_value: Mapped[int] = mapped_column(Integer)
