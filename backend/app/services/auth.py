"""Officer login, logout, sessions and password change."""

import math
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import get_settings
from app.core.errors import AccountLockedError, AuthenticationError, DomainError
from app.models import User, UserSession
from app.services import audit, captcha
from app.services import settings as app_settings
from app.services.user_ids import normalise_user_id

_INVALID = "The user ID or password is not correct."


def login(
    db: Session,
    *,
    user_id: str,
    password: str,
    captcha_id: str | None,
    captcha_answer: str | None,
) -> tuple[User, str, int]:
    """Check the captcha and credentials. Returns (user, session token, session seconds).

    Commits on every path: a used captcha and a failed attempt must be saved
    even though the request ends in an error.
    """
    if get_settings().captcha_enabled and not captcha.verify(db, captcha_id, captcha_answer):
        db.commit()
        raise DomainError("The captcha text is not correct. Please try the new one.")

    now = datetime.now(UTC)
    user = db.scalar(select(User).where(User.user_id == normalise_user_id(user_id)))

    if user is None or not user.is_active:
        security.verify_password(password, None)
        db.commit()
        raise AuthenticationError(_INVALID)

    if user.locked_until and user.locked_until > now:
        minutes = math.ceil((user.locked_until - now).total_seconds() / 60)
        db.commit()
        raise AccountLockedError(
            f"This account is locked after too many wrong passwords. "
            f"Try again after {minutes} minute(s)."
        )

    if not security.verify_password(password, user.password_hash):
        user.failed_attempts += 1
        max_attempts = app_settings.get_int(db, app_settings.LOGIN_MAX_FAILED_ATTEMPTS)
        if user.failed_attempts >= max_attempts:
            lock_minutes = app_settings.get_int(db, app_settings.LOGIN_LOCK_MINUTES)
            user.locked_until = now + timedelta(minutes=lock_minutes)
            user.failed_attempts = 0
            audit.record(
                db,
                actor=user,
                action="user.locked",
                entity_type="user",
                entity_id=user.id,
                entity_label=user.user_id,
                new={"locked_minutes": lock_minutes},
            )
        db.commit()
        raise AuthenticationError(_INVALID)

    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now

    hours = app_settings.get_int(db, app_settings.SESSION_HOURS)
    token = security.new_session_token()
    db.add(
        UserSession(
            token_hash=security.hash_token(token),
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(hours=hours),
        )
    )
    audit.record(
        db,
        actor=user,
        action="user.login",
        entity_type="user",
        entity_id=user.id,
        entity_label=user.user_id,
    )
    db.commit()
    return user, token, hours * 3600


def find_session(db: Session, token: str | None) -> UserSession | None:
    """The live session for a cookie token, or None."""
    if not token:
        return None
    session = db.scalar(
        select(UserSession).where(UserSession.token_hash == security.hash_token(token))
    )
    if session is None or session.revoked_at is not None:
        return None
    if session.expires_at <= datetime.now(UTC):
        return None
    if not session.user.is_active:
        return None
    return session


def revoke_sessions(db: Session, user: User, *, keep: UserSession | None = None) -> None:
    """End every session of a user, optionally keeping the current one."""
    statement = (
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    if keep is not None:
        statement = statement.where(UserSession.id != keep.id)
    db.execute(statement)


def logout(db: Session, session: UserSession) -> None:
    session.revoked_at = datetime.now(UTC)
    audit.record(
        db,
        actor=session.user,
        action="user.logout",
        entity_type="user",
        entity_id=session.user.id,
        entity_label=session.user.user_id,
    )


def change_password(
    db: Session,
    *,
    user: User,
    session: UserSession,
    current_password: str,
    new_password: str,
) -> None:
    if not security.verify_password(current_password, user.password_hash):
        raise DomainError("The current password is not correct.")
    if new_password == current_password:
        raise DomainError("The new password must be different from the current password.")
    problem = security.password_rule_problem(
        new_password,
        user_id=user.user_id,
        min_length=app_settings.get_int(db, app_settings.PASSWORD_MIN_LENGTH),
    )
    if problem:
        raise DomainError(problem)

    user.password_hash = security.hash_password(new_password)
    user.must_change_password = False
    revoke_sessions(db, user, keep=session)
    audit.record(
        db,
        actor=user,
        action="user.password_changed",
        entity_type="user",
        entity_id=user.id,
        entity_label=user.user_id,
    )
