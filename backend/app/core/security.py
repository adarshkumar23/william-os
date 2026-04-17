"""WILLIAM OS — Security utilities.
Cleaned version (M1): no HTTPException raised from core; `decode_token_safe` added for middleware.
"""

from __future__ import annotations

import base64
import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)


def create_access_token(user_id: uuid.UUID, extra_claims: dict | None = None) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        "iat": now,
        "type": "access",
        "jti": uuid.uuid4().hex,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "exp": now + timedelta(days=settings.jwt_refresh_token_expire_days),
        "iat": now,
        "type": "refresh",
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_token(token: str) -> dict:
    """Decode JWT. Raises jwt.InvalidTokenError / jwt.ExpiredSignatureError on failure.
    Call sites should convert to their own error type (e.g. AuthenticationError) — core stays framework-agnostic.
    """
    return jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
    )


def decode_token_safe(token: str) -> dict | None:
    """Non-raising variant for middleware. Returns None on any failure."""
    try:
        return decode_token(token)
    except Exception:
        return None


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=settings.encryption_iterations
    )
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_text(plaintext: str, passphrase: str) -> bytes:
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return salt + nonce + ciphertext


def decrypt_text(encrypted: bytes, passphrase: str) -> str:
    salt, nonce, ct = encrypted[:16], encrypted[16:28], encrypted[28:]
    key = _derive_key(passphrase, salt)
    return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")


def generate_device_fingerprint(user_agent: str, ip: str) -> str:
    return hashlib.sha256(f"{user_agent}:{ip}".encode()).hexdigest()[:16]


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _master_key() -> bytes:
    seed = settings.encryption_master_salt.get_secret_value().encode("utf-8")
    return hashlib.sha256(seed).digest()


def encrypt_api_secret(plaintext: str) -> str:
    nonce = os.urandom(12)
    ct = AESGCM(_master_key()).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ct).decode("utf-8")


def decrypt_api_secret(payload: str) -> str:
    raw = base64.urlsafe_b64decode(payload.encode("utf-8"))
    nonce, ct = raw[:12], raw[12:]
    return AESGCM(_master_key()).decrypt(nonce, ct, None).decode("utf-8")


# ── API Key helpers (C3 fix) ──────────────────────────────────────────────────
def hash_api_key(raw_key: str) -> str:
    """Salted-SHA256 hash for storage. The secret is `ENCRYPTION_MASTER_SALT`-scoped
    so an attacker needs both the DB row AND the master salt to brute-force."""
    salt = settings.encryption_master_salt.get_secret_value().encode("utf-8")
    return hashlib.sha256(salt + raw_key.encode("utf-8")).hexdigest()
