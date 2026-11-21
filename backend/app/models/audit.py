from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """One row per action or data change: who, when, old value, new value.

    Rows are immutable. A database trigger (see the migration) rejects every
    UPDATE, DELETE and TRUNCATE on this table.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    # The actor's user ID at the time, or "system:<name>". Kept as text so the
    # record still reads correctly after a user ID is renamed.
    actor_label: Mapped[str] = mapped_column(String(80))
    # An office may share one user ID, so the officer who acted is named on each action.
    officer_name: Mapped[str | None] = mapped_column(String(100))
    officer_designation: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64))
    entity_label: Mapped[str | None] = mapped_column(String(200))
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
