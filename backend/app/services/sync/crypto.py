from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
