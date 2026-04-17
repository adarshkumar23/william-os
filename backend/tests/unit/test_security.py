"""
WILLIAM OS — Security Unit Tests
Tests for JWT tokens, password hashing, and AES-256-GCM encryption.
"""

from __future__ import annotations

import uuid
from datetime import UTC

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decrypt_text,
    encrypt_text,
    generate_device_fingerprint,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "SecurePass123!"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("CorrectPassword1")
        assert not verify_password("WrongPassword1", hashed)

    def test_different_hashes_for_same_password(self):
        """Bcrypt uses random salt, so same input → different hashes."""
        h1 = hash_password("SamePass123")
        h2 = hash_password("SamePass123")
        assert h1 != h2
        assert verify_password("SamePass123", h1)
        assert verify_password("SamePass123", h2)


class TestJWT:
    def test_create_and_decode_access_token(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id, {"role": "owner"})
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"
        assert payload["role"] == "owner"
        assert "jti" in payload

    def test_create_and_decode_refresh_token(self):
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id)
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"

    def test_expired_token_rejected(self):
        from datetime import datetime, timedelta

        import jwt as pyjwt

        payload = {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(UTC) - timedelta(hours=1),
            "type": "access",
        }
        from app.core.config import get_settings

        settings = get_settings()
        token = pyjwt.encode(payload, settings.jwt_secret_key.get_secret_value(), algorithm="HS256")
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_token(token)

    def test_tampered_token_rejected(self):
        import jwt as pyjwt

        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_token(tampered)


class TestEncryption:
    def test_encrypt_and_decrypt(self):
        plaintext = "This is my private journal entry. 日本語テスト。"
        passphrase = "MySecretPhrase123"
        encrypted = encrypt_text(plaintext, passphrase)
        assert encrypted != plaintext.encode()
        assert len(encrypted) > len(plaintext)

        decrypted = decrypt_text(encrypted, passphrase)
        assert decrypted == plaintext

    def test_wrong_passphrase_fails(self):
        encrypted = encrypt_text("Secret data", "correct-passphrase")
        with pytest.raises(Exception):
            decrypt_text(encrypted, "wrong-passphrase")

    def test_different_encryptions_produce_different_output(self):
        """Random salt + nonce means same input → different ciphertext."""
        plaintext = "Same text"
        passphrase = "same-pass"
        e1 = encrypt_text(plaintext, passphrase)
        e2 = encrypt_text(plaintext, passphrase)
        assert e1 != e2
        assert decrypt_text(e1, passphrase) == plaintext
        assert decrypt_text(e2, passphrase) == plaintext

    def test_empty_string_encryption(self):
        encrypted = encrypt_text("", "pass")
        assert decrypt_text(encrypted, "pass") == ""

    def test_large_text_encryption(self):
        large_text = "A" * 100_000
        encrypted = encrypt_text(large_text, "pass")
        assert decrypt_text(encrypted, "pass") == large_text


class TestDeviceFingerprint:
    def test_deterministic(self):
        fp1 = generate_device_fingerprint("Mozilla/5.0", "192.168.1.1")
        fp2 = generate_device_fingerprint("Mozilla/5.0", "192.168.1.1")
        assert fp1 == fp2

    def test_different_inputs_different_fingerprints(self):
        fp1 = generate_device_fingerprint("Mozilla/5.0", "192.168.1.1")
        fp2 = generate_device_fingerprint("Chrome/120", "192.168.1.1")
        assert fp1 != fp2

    def test_fingerprint_length(self):
        fp = generate_device_fingerprint("ua", "ip")
        assert len(fp) == 16
