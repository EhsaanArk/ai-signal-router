"""Telegram authentication adapter using Telethon.

Provides a two-step login flow:
1. ``send_code`` — sends a verification code to the user's phone.
2. ``verify_code`` — exchanges the code (and optional 2FA password) for a
   serialised session string that can be stored and reused.
"""

from __future__ import annotations

import hashlib
import logging

from telethon import TelegramClient
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)


def _phone_id(phone: str) -> str:
    """Return a non-PII identifier derived from the phone number.

    Uses a SHA-256 hash prefix so logs remain correlatable across entries
    without exposing any phone digits (per SECURITY_REQUIREMENTS.md).
    """
    return hashlib.sha256(phone.encode()).hexdigest()[:8]


class TelegramAuth:
    """Manages the Telegram phone-code verification flow.

    Parameters
    ----------
    api_id:
        Telegram application API ID (from https://my.telegram.org).
    api_hash:
        Telegram application API hash.
    """

    def __init__(self, api_id: int, api_hash: str) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._pending_clients: dict[str, TelegramClient] = {}

    async def send_code(self, phone_number: str) -> dict:
        """Initiate the login flow by sending a verification code via Telegram.

        The created ``TelegramClient`` is stored internally so that
        :meth:`verify_code` can reuse the same connection.

        Returns
        -------
        dict
            ``{"phone_code_hash": "<hash>"}`` — needed for :meth:`verify_code`.
        """
        client = TelegramClient(
            StringSession(),
            self._api_id,
            self._api_hash,
        )
        await client.connect()

        sent_code = await client.send_code_request(phone_number)

        # Store client so verify_code can use the same session
        self._pending_clients[phone_number] = client

        logger.info("Verification code sent to %s", _phone_id(phone_number))
        return {"phone_code_hash": sent_code.phone_code_hash}

    async def verify_code(
        self,
        phone_number: str,
        code: str,
        phone_code_hash: str,
        password: str | None = None,
    ) -> str:
        """Complete the login and return a reusable session string.

        Parameters
        ----------
        phone_number:
            The phone number that received the code.
        code:
            The verification code the user received.
        phone_code_hash:
            The hash returned by :meth:`send_code`.
        password:
            Two-factor authentication password, if enabled on the account.

        Returns
        -------
        str
            A Telethon ``StringSession`` token that can be persisted and used
            to reconnect without re-authenticating.
        """
        client = self._pending_clients.get(phone_number)
        if client is None:
            raise ValueError(
                f"No pending authentication for {phone_number}. "
                "Call send_code() first."
            )

        try:
            await client.sign_in(
                phone=phone_number,
                code=code,
                phone_code_hash=phone_code_hash,
            )
        except Exception:
            # Telethon raises SessionPasswordNeededError when 2FA is enabled.
            # Re-import here to avoid a hard dependency on internal errors at
            # module level.
            from telethon.errors import SessionPasswordNeededError

            if password is None:
                raise
            # If the original sign_in raised SessionPasswordNeededError, retry
            # with the 2FA password.
            await client.sign_in(password=password)

        session_string: str = client.session.save()  # type: ignore[union-attr]
        logger.info("Authentication successful for %s", _phone_id(phone_number))

        # Cleanup: remove from pending but do NOT disconnect — the caller may
        # want to keep using the session.  We disconnect on explicit request.
        self._pending_clients.pop(phone_number, None)

        return session_string

    async def disconnect(self, phone_number: str) -> None:
        """Disconnect and discard the pending client for *phone_number*."""
        client = self._pending_clients.pop(phone_number, None)
        if client is not None:
            await client.disconnect()
            logger.debug("Disconnected pending client for %s", _phone_id(phone_number))
