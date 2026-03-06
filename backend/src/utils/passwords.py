"""Password hashing helpers for admin users."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Hash password with PBKDF2-HMAC-SHA256."""

    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return (
        f"pbkdf2_sha256${_PBKDF2_ITERATIONS}$"
        f"{base64.urlsafe_b64encode(salt).decode('utf-8')}$"
        f"{base64.urlsafe_b64encode(digest).decode('utf-8')}"
    )


def verify_password(password: str, encoded: str) -> bool:
    """Verify password against encoded hash."""

    try:
        algorithm, iterations_text, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = base64.urlsafe_b64decode(salt_b64.encode("utf-8"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("utf-8"))
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)
