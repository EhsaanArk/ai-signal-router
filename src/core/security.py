"""Encryption utilities for Telegram session string storage.

Uses Fernet symmetric encryption from the ``cryptography`` library to
encrypt/decrypt session strings at rest.  The encryption key is derived
from the ``ENCRYPTION_KEY`` environment variable.
"""

from __future__ import annotations

import base64

from cryptography.fernet import Fernet


def generate_key() -> bytes:
    """Generate a new Fernet encryption key.

    Returns
    -------
    bytes
        A URL-safe base64-encoded 32-byte key suitable for use with
        ``cryptography.fernet.Fernet``.
    """
    return Fernet.generate_key()


def encrypt_session(plain: str, key: bytes) -> str:
    """Encrypt a plaintext Telegram session string.

    Parameters
    ----------
    plain:
        The plaintext session string to encrypt.
    key:
        A Fernet-compatible encryption key (as returned by
        ``generate_key()``).

    Returns
    -------
    str
        The encrypted session string, encoded as a URL-safe base64 string.
    """
    fernet = Fernet(key)
    encrypted: bytes = fernet.encrypt(plain.encode("utf-8"))
    return base64.urlsafe_b64encode(encrypted).decode("utf-8")


def decrypt_session(cipher: str, key: bytes) -> str:
    """Decrypt an encrypted Telegram session string.

    Parameters
    ----------
    cipher:
        The encrypted session string (URL-safe base64) as returned by
        ``encrypt_session()``.
    key:
        The same Fernet key that was used for encryption.

    Returns
    -------
    str
        The original plaintext session string.

    Raises
    ------
    cryptography.fernet.InvalidToken
        If the key is wrong or the ciphertext has been tampered with.
    """
    fernet = Fernet(key)
    encrypted: bytes = base64.urlsafe_b64decode(cipher.encode("utf-8"))
    return fernet.decrypt(encrypted).decode("utf-8")
