"""Errors raised by the services and turned into JSON answers in app.main."""


class DomainError(Exception):
    """A request that breaks a rule. `errors` lists row-level problems of a bulk upload."""

    status_code = 400

    def __init__(self, message: str, *, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors or []
        # Extra keys to add to the JSON answer.
        self.extra: dict[str, object] = {}


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409


class AuthenticationError(DomainError):
    status_code = 401


class PermissionDeniedError(DomainError):
    status_code = 403


class AccountLockedError(DomainError):
    status_code = 423


class TooManyRequestsError(DomainError):
    status_code = 429


class FormError(DomainError):
    """A form that breaks one or more rules. `field_errors` maps a field name to its message."""

    status_code = 422

    def __init__(self, field_errors: dict[str, str]) -> None:
        super().__init__("Please correct the highlighted fields.")
        self.field_errors = field_errors
