"""Tests for src.core.security — AES-256-GCM encrypt/decrypt utilities."""

import base64
import ipaddress

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.fernet import Fernet

from src.core.security import (
    decrypt_session,
    decrypt_session_auto,
    decrypt_session_legacy,
    encrypt_session,
    generate_key,
    validate_outbound_webhook_url,
)


def test_encrypt_decrypt_roundtrip():
    """Encrypting then decrypting should return the original plaintext."""
    key = generate_key()
    plaintext = "my-secret-session-string"
    cipher = encrypt_session(plaintext, key)
    assert decrypt_session(cipher, key) == plaintext


def test_different_keys_fail():
    """Decrypting with a different key should raise InvalidTag."""
    key1 = generate_key()
    key2 = generate_key()
    cipher = encrypt_session("secret", key1)
    with pytest.raises(InvalidTag):
        decrypt_session(cipher, key2)


def test_generate_key():
    """Generated key should be a valid url-safe base64-encoded 32-byte key."""
    key = generate_key()
    assert isinstance(key, bytes)
    decoded = base64.urlsafe_b64decode(key)
    assert len(decoded) == 32


def test_ciphertext_differs_each_call():
    """Each encryption should produce different ciphertext (unique nonce)."""
    key = generate_key()
    c1 = encrypt_session("same-text", key)
    c2 = encrypt_session("same-text", key)
    assert c1 != c2
    # But both decrypt to the same plaintext
    assert decrypt_session(c1, key) == decrypt_session(c2, key) == "same-text"


def test_legacy_fernet_decrypt():
    """Legacy Fernet-encrypted strings should be decryptable."""
    key = generate_key()  # base64-encoded 32 bytes — valid Fernet key
    fernet = Fernet(key)
    plaintext = "legacy-session-string"
    cipher = fernet.encrypt(plaintext.encode()).decode()
    assert decrypt_session_legacy(cipher, key) == plaintext


def test_auto_decrypt_aes256gcm():
    """Auto-decrypt should handle AES-256-GCM ciphertext."""
    key = generate_key()
    cipher = encrypt_session("aes-gcm-session", key)
    assert decrypt_session_auto(cipher, key) == "aes-gcm-session"


def test_auto_decrypt_fernet_fallback():
    """Auto-decrypt should fall back to Fernet for legacy ciphertext."""
    key = generate_key()
    fernet = Fernet(key)
    cipher = fernet.encrypt(b"legacy-session").decode()
    assert decrypt_session_auto(cipher, key) == "legacy-session"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/webhook",
        "https://127.0.0.1/hook",
        "https://10.0.0.1/hook",
        "https://172.16.0.1/hook",
        "https://192.168.1.2/hook",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/hook",
        "https://[fd00::1]/hook",
        "https://metadata.google.internal/hook",
        "http://localhost./hook",
    ],
)
def test_validate_outbound_webhook_url_blocks_private_targets(url: str):
    allowed, reason, _ips = validate_outbound_webhook_url(url, local_mode=False)
    assert allowed is False
    assert reason


@pytest.mark.parametrize(
    "url",
    [
        "https://93.184.216.34/webhook",
        "http://1.1.1.1/hook",
    ],
)
def test_validate_outbound_webhook_url_allows_public_targets(url: str):
    allowed, reason, resolved_ips = validate_outbound_webhook_url(url, local_mode=False)
    assert allowed is True
    assert reason is None
    assert resolved_ips is not None and len(resolved_ips) > 0


def test_validate_outbound_webhook_url_returns_resolved_ips_for_hostname(monkeypatch):
    public_ip = ipaddress.ip_address("93.184.216.34")
    monkeypatch.setattr(
        "src.core.security._resolve_host_ips",
        lambda host, timeout_seconds=2.0: ({public_ip}, None),
    )
    allowed, reason, resolved_ips = validate_outbound_webhook_url(
        "https://example.com/webhook",
        local_mode=False,
    )
    assert allowed is True
    assert resolved_ips == {public_ip}


def test_validate_outbound_webhook_url_blocks_hostname_resolving_to_private_ip(monkeypatch):
    monkeypatch.setattr(
        "src.core.security._resolve_host_ips",
        lambda host, timeout_seconds=2.0: ({ipaddress.ip_address("127.0.0.1")}, None),
    )
    allowed, reason, _ips = validate_outbound_webhook_url(
        "https://public.example/webhook",
        local_mode=False,
    )
    assert allowed is False
    assert reason


def test_validate_outbound_webhook_url_allows_hostname_resolving_to_public_ip(monkeypatch):
    monkeypatch.setattr(
        "src.core.security._resolve_host_ips",
        lambda host, timeout_seconds=2.0: ({ipaddress.ip_address("93.184.216.34")}, None),
    )
    allowed, reason, _ips = validate_outbound_webhook_url(
        "https://public.example/webhook",
        local_mode=False,
    )
    assert allowed is True
    assert reason is None


def test_validate_outbound_webhook_url_fails_closed_on_dns_error_in_non_local(monkeypatch):
    monkeypatch.setattr(
        "src.core.security._resolve_host_ips",
        lambda host, timeout_seconds=2.0: (set(), "Unable to resolve host"),
    )
    allowed, reason, _ips = validate_outbound_webhook_url(
        "https://public.example/webhook",
        local_mode=False,
    )
    assert allowed is False
    assert reason


def test_validate_outbound_webhook_url_fails_open_on_dns_error_in_local_mode(monkeypatch):
    monkeypatch.setattr(
        "src.core.security._resolve_host_ips",
        lambda host, timeout_seconds=2.0: (set(), "Unable to resolve host"),
    )
    allowed, reason, _ips = validate_outbound_webhook_url(
        "https://public.example/webhook",
        local_mode=True,
    )
    assert allowed is True
    assert reason is None
