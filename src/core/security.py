"""Encryption utilities for Telegram session string storage.

Uses AES-256-GCM authenticated encryption from the ``cryptography`` library
to encrypt/decrypt session strings at rest.  The encryption key is derived
from the ``ENCRYPTION_KEY`` environment variable (URL-safe base64-encoded
32-byte key).
"""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import hashlib
import ipaddress
import os
import socket
from urllib.parse import urlparse

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.fernet import Fernet, InvalidToken

_NONCE_SIZE = 12  # 96-bit nonce recommended for AES-GCM
_ALLOWED_WEBHOOK_SCHEMES = {"http", "https"}
_BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "instance-data",
    "metadata.azure.internal",
    "metadata.aliyun.internal",
}
_BLOCKED_METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("100.100.100.200"),
}
_DNS_TIMEOUT_SECONDS = 2.0
_DNS_RESOLVER_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="webhook-dns")


def generate_key() -> bytes:
    """Generate a new AES-256 encryption key.

    Returns
    -------
    bytes
        A URL-safe base64-encoded 32-byte key, compatible with the
        ``ENCRYPTION_KEY`` environment variable format.
    """
    raw = AESGCM.generate_key(bit_length=256)
    return base64.urlsafe_b64encode(raw)


def _get_raw_key(key: bytes) -> bytes:
    """Decode a base64-encoded key to raw 32 bytes."""
    return base64.urlsafe_b64decode(key)


def encrypt_session(plain: str, key: bytes) -> str:
    """Encrypt a plaintext Telegram session string with AES-256-GCM.

    Parameters
    ----------
    plain:
        The plaintext session string to encrypt.
    key:
        A URL-safe base64-encoded 32-byte encryption key.

    Returns
    -------
    str
        The encrypted session string as a URL-safe base64 string
        (nonce + ciphertext concatenated).
    """
    raw_key = _get_raw_key(key)
    aesgcm = AESGCM(raw_key)
    nonce = os.urandom(_NONCE_SIZE)
    ciphertext = aesgcm.encrypt(nonce, plain.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_session(cipher: str, key: bytes) -> str:
    """Decrypt an AES-256-GCM encrypted Telegram session string.

    Parameters
    ----------
    cipher:
        The encrypted session string (URL-safe base64) as returned by
        ``encrypt_session()``.
    key:
        The same key that was used for encryption.

    Returns
    -------
    str
        The original plaintext session string.

    Raises
    ------
    cryptography.exceptions.InvalidTag
        If the key is wrong or the ciphertext has been tampered with.
    """
    raw_key = _get_raw_key(key)
    aesgcm = AESGCM(raw_key)
    data = base64.urlsafe_b64decode(cipher.encode("utf-8"))
    nonce = data[:_NONCE_SIZE]
    ciphertext = data[_NONCE_SIZE:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


def decrypt_session_legacy(cipher: str, key: bytes) -> str:
    """Decrypt a Fernet-encrypted session string (legacy format).

    Used during migration from the old Fernet encryption scheme.

    Parameters
    ----------
    cipher:
        The Fernet-encrypted session string.
    key:
        The encryption key (same base64 format used for AES-256-GCM).

    Returns
    -------
    str
        The original plaintext session string.
    """
    fernet = Fernet(key)
    return fernet.decrypt(cipher.encode("utf-8")).decode("utf-8")


def decrypt_session_auto(cipher: str, key: bytes) -> str:
    """Decrypt a session string, trying AES-256-GCM first then Fernet.

    Parameters
    ----------
    cipher:
        The encrypted session string (either AES-256-GCM or Fernet format).
    key:
        The encryption key.

    Returns
    -------
    str
        The original plaintext session string.
    """
    try:
        return decrypt_session(cipher, key)
    except Exception:
        return decrypt_session_legacy(cipher, key)


def sha256_hex(value: str) -> str:
    """Return the SHA-256 hex digest for *value*."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_blocked_ip(ip_obj: ipaddress._BaseAddress) -> bool:
    """Return True for IPs that should never be used as outbound webhooks."""
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
        or ip_obj.is_reserved
        or ip_obj in _BLOCKED_METADATA_IPS
    )


def _resolve_host_ips(
    host: str,
    timeout_seconds: float = _DNS_TIMEOUT_SECONDS,
) -> tuple[set[ipaddress._BaseAddress], str | None]:
    """Resolve host to IPs with a bounded timeout."""

    def _lookup() -> set[str]:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return {info[4][0] for info in infos if info[4]}

    try:
        ip_values = _DNS_RESOLVER_POOL.submit(_lookup).result(timeout=timeout_seconds)
    except FuturesTimeoutError:
        return set(), "DNS resolution timed out"
    except socket.gaierror:
        return set(), "Unable to resolve host"
    except Exception:
        return set(), "Unable to resolve host"

    resolved: set[ipaddress._BaseAddress] = set()
    for value in ip_values:
        try:
            resolved.add(ipaddress.ip_address(value))
        except ValueError:
            continue

    if not resolved:
        return set(), "Unable to resolve host"
    return resolved, None


def _is_local_mode(local_mode: bool | None) -> bool:
    """Resolve local mode from explicit argument or environment."""
    if local_mode is not None:
        return local_mode
    return os.environ.get("LOCAL_MODE", "true").lower() in ("true", "1", "yes")


def validate_outbound_webhook_url(
    url: str,
    *,
    local_mode: bool | None = None,
) -> tuple[bool, str | None, set[ipaddress._BaseAddress] | None]:
    """Validate a user-provided webhook URL against SSRF-sensitive targets.

    Returns (allowed, reason_or_None, resolved_ips_or_None).  The third
    element contains the validated IP addresses so callers can pin DNS and
    prevent rebinding attacks.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False, "Invalid URL", None

    if parsed.scheme not in _ALLOWED_WEBHOOK_SCHEMES:
        return False, "URL must use http or https", None

    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return False, "URL must include a valid host", None

    if host in _BLOCKED_HOSTNAMES or host.endswith(".localhost"):
        return False, "Webhook host is not allowed", None

    try:
        ip_obj = ipaddress.ip_address(host)
    except ValueError:
        ip_obj = None

    if ip_obj and _is_blocked_ip(ip_obj):
        return False, "Webhook target resolves to a private or restricted IP address", None

    if ip_obj is not None:
        return True, None, {ip_obj}

    resolved_ips, resolve_error = _resolve_host_ips(host)
    if resolve_error:
        if _is_local_mode(local_mode):
            return True, None, None
        return False, "Webhook host could not be resolved safely", None
    if any(_is_blocked_ip(resolved_ip) for resolved_ip in resolved_ips):
        return False, "Webhook target resolves to a private or restricted IP address", None

    return True, None, resolved_ips
