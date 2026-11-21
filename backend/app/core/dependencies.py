"""Request dependencies: the logged-in officer and permission checks.

Authorisation is always decided here in the backend, never by the UI.
"""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.models import Role, User, UserSession
from app.services import auth

SESSION_COOKIE = "pp_session"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def require_fetch_header(request: Request) -> None:
    """Refuse state-changing requests that do not come from the portal's own pages.

    The login cookie is sent by the browser automatically, so another website
    could try to post a form to the API. A browser will not let another site
    add a custom header without the API's permission, and the API gives none.
    """
    if request.method not in _SAFE_METHODS and request.headers.get("x-requested-with") != "fetch":
        raise PermissionDeniedError("This request did not come from the portal.")


@dataclass(frozen=True)
class CurrentSession:
    user: User
    session: UserSession


def get_current_session(request: Request, db: Session = Depends(get_db)) -> CurrentSession:
    session = auth.find_session(db, request.cookies.get(SESSION_COOKIE))
    if session is None:
        raise AuthenticationError("Please log in.")
    return CurrentSession(user=session.user, session=session)


def get_current_user(current: CurrentSession = Depends(get_current_session)) -> User:
    """The logged-in officer. Blocked until a generated password has been changed."""
    if current.user.must_change_password:
        raise PermissionDeniedError("Change your password before continuing.")
    return current.user


def require_roles(*roles: Role) -> Callable[[User], User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise PermissionDeniedError("You do not have permission to do this.")
        return user

    return dependency


require_state_admin = require_roles(Role.STATE_ADMIN)
