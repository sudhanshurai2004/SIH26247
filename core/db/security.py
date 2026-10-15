"""Local PIN hashing and role-authorization helpers."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from collections.abc import Iterable

from core.db.models import Role, User

PIN_PATTERN = re.compile(r"^\d{4,12}$")
PBKDF2_ITERATIONS = 600_000


class AuthorizationError(PermissionError):
    """Raised when a local actor lacks the required role or ownership."""


class PinValidationError(ValueError):
    """Raised when a PIN does not meet the local offline-login constraints."""


def hash_pin(pin: str, *, salt: bytes | None = None) -> str:
    """Return a salted PBKDF2-SHA256 PIN hash; plaintext is never persisted."""
    _validate_pin(pin)
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, encoded_hash: str) -> bool:
    """Verify a candidate PIN using constant-time digest comparison."""
    if not isinstance(pin, str):
        return False
    try:
        algorithm, iterations_text, salt_hex, expected_digest = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
    except (TypeError, ValueError):
        return False

    candidate_digest = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        salt,
        iterations,
    ).hex()
    return hmac.compare_digest(candidate_digest, expected_digest)


def require_role(user: User | None, allowed_roles: Iterable[Role]) -> User:
    """Require a persisted local user to hold one of the explicit roles."""
    if user is None:
        raise AuthorizationError("actor does not exist")
    allowed = {role.value for role in allowed_roles}
    if user.role not in allowed:
        raise AuthorizationError("actor does not have the required role")
    return user


def _validate_pin(pin: str) -> None:
    if not isinstance(pin, str) or not PIN_PATTERN.fullmatch(pin):
        raise PinValidationError("PIN must contain 4 to 12 digits")
