"""Re-encrypt Telegram session strings from Fernet to AES-256-GCM.

Revision ID: 016
Revises: 015
Create Date: 2026-03-15

"""
from typing import Sequence, Union

import os
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Re-encrypt all session strings from Fernet to AES-256-GCM."""
    from cryptography.fernet import Fernet
    from src.core.security import encrypt_session

    encryption_key = os.environ.get("ENCRYPTION_KEY")
    if not encryption_key:
        # No key configured — skip (no sessions to migrate)
        return

    key_bytes = encryption_key.encode()
    fernet = Fernet(key_bytes)

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, session_string_encrypted FROM telegram_sessions")
    ).fetchall()

    for row in rows:
        session_id, encrypted_value = row
        if not encrypted_value:
            continue
        try:
            # Decrypt with old Fernet scheme
            plaintext = fernet.decrypt(encrypted_value.encode()).decode()
            # Re-encrypt with AES-256-GCM
            new_encrypted = encrypt_session(plaintext, key_bytes)
            conn.execute(
                sa.text(
                    "UPDATE telegram_sessions SET session_string_encrypted = :val WHERE id = :id"
                ),
                {"val": new_encrypted, "id": session_id},
            )
        except Exception:
            # Already migrated or invalid — skip
            pass


def downgrade() -> None:
    """Re-encrypt all session strings from AES-256-GCM back to Fernet."""
    from cryptography.fernet import Fernet
    from src.core.security import decrypt_session

    encryption_key = os.environ.get("ENCRYPTION_KEY")
    if not encryption_key:
        return

    key_bytes = encryption_key.encode()
    fernet = Fernet(key_bytes)

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, session_string_encrypted FROM telegram_sessions")
    ).fetchall()

    for row in rows:
        session_id, encrypted_value = row
        if not encrypted_value:
            continue
        try:
            plaintext = decrypt_session(encrypted_value, key_bytes)
            old_encrypted = fernet.encrypt(plaintext.encode()).decode()
            conn.execute(
                sa.text(
                    "UPDATE telegram_sessions SET session_string_encrypted = :val WHERE id = :id"
                ),
                {"val": old_encrypted, "id": session_id},
            )
        except Exception:
            pass
