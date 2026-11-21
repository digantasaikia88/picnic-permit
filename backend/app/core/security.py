"""Password hashing, password rules and session tokens."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# Argon2id at the OWASP minimum (19 MiB, 2 passes). Strong enough for officer
# passwords and quick enough to issue first passwords to 376 accounts in one request.
_hasher = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)

# A fixed hash, verified when the user ID does not exist, so that a login
# attempt takes the same time whether or not the account exists.
_DUMMY_HASH = _hasher.hash("not-a-real-password")

# No 0/O, 1/l/I: generated passwords are read out and typed by hand.
_PASSWORD_LETTERS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
_PASSWORD_DIGITS = "23456789"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and bool(password_hash)
    except VerificationError, InvalidHashError:
        return False


def generate_password(length: int) -> str:
    """A random password with at least one letter and one digit."""
    alphabet = _PASSWORD_LETTERS + _PASSWORD_DIGITS
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c in _PASSWORD_DIGITS for c in password) and any(
            c in _PASSWORD_LETTERS for c in password
        ):
            return password


def password_rule_problem(password: str, *, user_id: str, min_length: int) -> str | None:
    """Return why the password breaks the rule, or None if it is acceptable."""
    if len(password) < min_length:
        return f"The password must have at least {min_length} characters."
    if len(password) > 128:
        return "The password must have at most 128 characters."
    if not any(c.isalpha() for c in password):
        return "The password must contain at least 1 letter."
    if not any(c.isdigit() for c in password):
        return "The password must contain at least 1 digit."
    if password.lower() == user_id.lower():
        return "The password must not be the same as the user ID."
    return None


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Session tokens are long and random, so a plain SHA-256 is enough."""
    return hashlib.sha256(token.encode()).hexdigest()
