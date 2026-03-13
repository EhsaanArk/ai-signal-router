"""Tests for src.core.security — Fernet encrypt/decrypt utilities."""

import base64

import pytest
from cryptography.fernet import InvalidToken

from src.core.security import decrypt_session, encrypt_session, generate_key


def test_encrypt_decrypt_roundtrip():
    """Encrypting then decrypting should return the original plaintext."""
    key = generate_key()
    plaintext = "my-secret-session-string"
    cipher = encrypt_session(plaintext, key)
    assert decrypt_session(cipher, key) == plaintext


def test_different_keys_fail():
    """Decrypting with a different key should raise InvalidToken."""
    key1 = generate_key()
    key2 = generate_key()
    cipher = encrypt_session("secret", key1)
    with pytest.raises(InvalidToken):
        decrypt_session(cipher, key2)


def test_generate_key():
    """Generated key should be a valid url-safe base64-encoded 32-byte key."""
    key = generate_key()
    assert isinstance(key, bytes)
    # Fernet keys are 44 bytes of url-safe base64 (encoding 32 bytes)
    decoded = base64.urlsafe_b64decode(key)
    assert len(decoded) == 32
