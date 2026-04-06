"""
WILLIAM OS — Security Utilities
JWT tokens, password hashing, AES-256-GCM encryption for journal vault.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# ── Password Hashing ────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT Tokens ───────────────────────────────────────────────────

class TokenPayload:
    def __init__(self, sub: str, exp: datetime, token_type: str, jti: str):
        self.sub = sub
        self.exp = exp
        self.token_type = token_type
        self.jti = jti


def create_access_token(user_id: uuid.UUID, extra_claims: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
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
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "exp": now + timedelta(days=settings.jwt_refresh_token_expire_days),
        "iat": now,
        "type": "refresh",
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.InvalidTokenError on failure."""
    return jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
    )


# ── AES-256-GCM Encryption (Journal Vault) ──────────────────────

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from user passphrase using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=settings.encryption_iterations,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_text(plaintext: str, passphrase: str) -> bytes:
    """
    Encrypt text with AES-256-GCM.
    Returns: salt (16) + nonce (12) + ciphertext (variable)
    """
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return salt + nonce + ciphertext


def decrypt_text(encrypted: bytes, passphrase: str) -> str:
    """Decrypt AES-256-GCM encrypted data. Raises on wrong passphrase."""
    salt = encrypted[:16]
    nonce = encrypted[16:28]
    ciphertext = encrypted[28:]
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def generate_device_fingerprint(user_agent: str, ip: str) -> str:
    """Deterministic device fingerprint for multi-device tracking."""
    raw = f"{user_agent}:{ip}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
