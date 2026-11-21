"""Writes rows to the immutable audit log."""

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User

SYSTEM_SEED = "system:seed"
SYSTEM_CLI = "system:cli"


def record(
    db: Session,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: int | str | None = None,
    entity_label: str | None = None,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
    system_label: str = SYSTEM_CLI,
    officer_name: str | None = None,
    officer_designation: str | None = None,
) -> None:
    """Add one audit row to the session. Passwords are never passed in here."""
    db.add(
        AuditLog(
            actor_user_id=actor.id if actor else None,
            actor_label=actor.user_id if actor else system_label,
            officer_name=officer_name,
            officer_designation=officer_designation,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            entity_label=entity_label,
            old_value=old,
            new_value=new,
        )
    )


def changed_fields(
    before: dict[str, Any], after: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Keep only the keys whose value changed."""
    keys = [k for k in after if before.get(k) != after[k]]
    return {k: before.get(k) for k in keys}, {k: after[k] for k in keys}
