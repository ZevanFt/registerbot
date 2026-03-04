"""Encryption helpers based on cryptography.fernet."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def _normalize_key(key: str) -> bytes:
    if key:
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)
    return Fernet.generate_key()


def encrypt_text(text: str, key: str) -> str:
    """Encrypt plaintext into URL-safe token string."""

    fernet = Fernet(_normalize_key(key))
    return fernet.encrypt(text.encode("utf-8")).decode("utf-8")


def decrypt_text(encrypted: str, key: str) -> str:
    """Decrypt token string into plaintext."""

    fernet = Fernet(_normalize_key(key))
    return fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")


def generate_key() -> str:
    """Generate a new Fernet key string."""

    return Fernet.generate_key().decode("utf-8")
