"""Cryptography helpers: secret encryption, password hashing and access tokens.

* All keys are derived from ``SECRET_KEY`` with HKDF-SHA256 and a distinct ``info`` label, so the JWT signing key
  and the encryption key never share key material.
* Secrets (the Keitaro API key) are encrypted with Fernet (AES-128-CBC + HMAC-SHA256, authenticated).
  Ciphertexts created by v1.0 (key = sha256(SECRET_KEY)) are still readable and are re-encrypted on the next save.
* Passwords are hashed with scrypt (memory-hard, stdlib) and a random 16-byte salt.
"""
import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import jwt
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import get_settings

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "keitaro-manager"


class SecretDecryptionError(Exception):
    """Raised when a stored secret cannot be decrypted (e.g. SECRET_KEY was changed)."""


class InvalidTokenError(Exception):
    """Access token is malformed, expired or has a wrong signature."""


# ----------------------------------------------------------------------------- keys
def derive_key(purpose: str, secret: str | None = None) -> bytes:
    secret = secret if secret is not None else get_settings().secret_key
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"keitaro-manager/v1", info=purpose.encode())
    return hkdf.derive(secret.encode("utf-8"))


@lru_cache(maxsize=4)
def _fernet(secret: str) -> MultiFernet:
    current = Fernet(base64.urlsafe_b64encode(derive_key("secret-encryption", secret)))
    legacy = Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest()))
    return MultiFernet([current, legacy])


def encrypt_secret(value: str) -> str:
    return _fernet(get_settings().secret_key).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet(get_settings().secret_key).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise SecretDecryptionError("Не удалось расшифровать API-ключ. Проверьте SECRET_KEY.") from exc


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "••••••"
    return f"{value[:2]}••••••{value[-2:]}"


# ------------------------------------------------------------------------ passwords
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    b64 = base64.b64encode
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${b64(salt).decode()}${b64(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, n, r, p, salt_b64, hash_b64 = encoded.split("$")
        if algo != "scrypt":
            return False
        expected = base64.b64decode(hash_b64)
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.b64decode(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)


# A valid hash of a random password: used to spend the same time when the user does not exist.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


# --------------------------------------------------------------------------- tokens
def create_access_token(user_id: int, username: str, ttl_minutes: int | None = None) -> tuple[str, datetime]:
    ttl = ttl_minutes or get_settings().access_token_ttl_minutes
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=ttl)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "name": username,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "iss": JWT_ISSUER,
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, derive_key("jwt-signing"), algorithm=JWT_ALGORITHM), expires


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            derive_key("jwt-signing"),
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["sub", "exp", "iat", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
