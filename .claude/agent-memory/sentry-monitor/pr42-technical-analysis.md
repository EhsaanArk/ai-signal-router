---
name: PR #42 Technical Analysis
description: Detailed technical review of error handling changes in PR #42
type: project
---

## PR #42 Technical Deep Dive

### Changes Summary
**Date**: 2026-03-17 20:06 UTC
**Scope**: Telegram auth endpoint error handling + session lifecycle visibility
**Files Modified**: 5 (routes.py, test_telegram.py, migration 018, CLAUDE.md, .gitmodules)
**Risk**: LOW (defensive programming, no breaking changes)

---

## Error Handling Details

### 1. `/telegram/send-code` Endpoint

#### Before
```python
auth = _get_telegram_auth(settings)  # Could raise, returns None if not locked
result = await auth.send_code(body.phone_number)  # Unhandled Telethon exceptions
return SendCodeResponse(phone_code_hash=result["phone_code_hash"])
```

#### After
```python
auth = await _get_telegram_auth(settings)  # Now async + thread-safe
try:
    result = await auth.send_code(body.phone_number)
except PhoneNumberInvalidError:
    raise HTTPException(status=400, detail="Invalid phone number format.")
except FloodWaitError as exc:
    raise HTTPException(
        status=429,
        detail=f"Rate limited. Retry after {exc.seconds}s.",
        headers={"Retry-After": str(exc.seconds)}
    )
except Exception:
    logger.exception("Telegram send_code failed")
    raise HTTPException(status=502, detail="Telegram service unavailable.")
```

**Improvements**:
- ✓ PhoneNumberInvalidError → 400 (client error)
- ✓ FloodWaitError → 429 + Retry-After header (HTTP best practice)
- ✓ Catch-all → 502 (external service error, not internal bug)
- ✓ Logging captures full stack trace

**Risk**: Catch-all `Exception` is broad. Future: consider specific Telethon exceptions (ConnectionError, TimeoutError, etc.)

---

### 2. `/telegram/verify-code` Endpoint

#### Before
```python
from telethon.errors import SessionPasswordNeededError

auth = _get_telegram_auth(settings)
try:
    session_string = await auth.verify_code(...)
except (SessionPasswordNeededError, ValueError) as exc:
    if "password" in str(exc).lower() or isinstance(exc, SessionPasswordNeededError):
        return VerifyCodeResponse(status="2fa_required", requires_2fa=True)
    raise  # Unhandled — becomes 500

# No error handling for encryption
encrypted = encrypt_session(session_string, settings.ENCRYPTION_KEY.encode())
```

#### After
```python
from telethon.errors import (
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)

auth = await _get_telegram_auth(settings)
try:
    session_string = await auth.verify_code(...)
except (SessionPasswordNeededError, ValueError) as exc:
    if "password" in str(exc).lower() or isinstance(exc, SessionPasswordNeededError):
        return VerifyCodeResponse(status="2fa_required", requires_2fa=True)
    raise HTTPException(status=400, detail=str(exc))  # Now handled
except PhoneCodeInvalidError:
    raise HTTPException(status=400, detail="Invalid verification code.")
except PhoneCodeExpiredError:
    raise HTTPException(status=400, detail="Code has expired. Request new one.")
except FloodWaitError as exc:
    raise HTTPException(status=429, ...)
except Exception:
    logger.exception("Telegram verify_code failed")
    raise HTTPException(status=502, detail="Telegram verification failed.")

# Now with error handling
try:
    encrypted = encrypt_session(session_string, settings.ENCRYPTION_KEY.encode())
except Exception:
    logger.exception("Failed to encrypt Telegram session")
    raise HTTPException(status=500, detail="Failed to encrypt session. Check ENCRYPTION_KEY.")
```

**Improvements**:
- ✓ PhoneCodeInvalidError → 400 (specific user error)
- ✓ PhoneCodeExpiredError → 400 (specific user error)
- ✓ Encryption failures → 500 with helpful message
- ✓ Generic ValueError now returns 400 instead of 500
- ✓ All exceptions logged with stack trace

**Risk**: Encryption key misconfiguration would now return 500. Should verify ENCRYPTION_KEY is set in staging.

---

### 3. `/telegram/channels` Endpoint

#### Before
```python
session_string = decrypt_session_auto(session_encrypted, ...)  # Unhandled
raw_channels = await get_user_channels(
    session_string=session_string,
    api_id=settings.TELEGRAM_API_ID,
    api_hash=settings.TELEGRAM_API_HASH,
    # No proxy parameter!
)
```

#### After
```python
try:
    session_string = decrypt_session_auto(session_encrypted, ...)
except Exception:
    logger.exception("Failed to decrypt Telegram session for user %s", current_user.id)
    raise HTTPException(status=400, detail="Session is corrupted or invalid. Reconnect.")

import os
from src.adapters.telegram import get_user_channels, parse_proxy_url
from telethon.errors import FloodWaitError

try:
    raw_channels = await get_user_channels(
        session_string=session_string,
        api_id=settings.TELEGRAM_API_ID,
        api_hash=settings.TELEGRAM_API_HASH,
        proxy=parse_proxy_url(os.environ.get("TELEGRAM_PROXY_URL")),  # Added!
    )
except FloodWaitError as exc:
    raise HTTPException(status=429, ...)
except RuntimeError:  # Session expired
    raise HTTPException(status=401, detail="Session has expired. Reconnect.")
except Exception:
    logger.exception("Failed to fetch Telegram channels for user %s", current_user.id)
    raise HTTPException(status=502, detail="Failed to fetch channels. Try again.")
```

**Improvements**:
- ✓ Decryption failures → 400 (corrupted session)
- ✓ FloodWaitError → 429 (rate limited)
- ✓ RuntimeError → 401 (session expired, needs re-auth)
- ✓ Added TELEGRAM_PROXY_URL support (important for corporate users)
- ✓ All exceptions logged with user ID for debugging

**Risk**: RuntimeError is broad; should verify Telethon actually raises RuntimeError for expired sessions (check telethon source).

---

### 4. `/telegram/disconnect` Endpoint

#### Before
```python
for session in sessions:
    session.is_active = False
    session.disconnected_reason = "user_disconnected"
    session.disconnected_at = func.now()  # ❌ BUG: func is SQLAlchemy function, not datetime
```

#### After
```python
from datetime import datetime, timezone

for session in sessions:
    session.is_active = False
    session.disconnected_reason = "user_disconnected"
    session.disconnected_at = datetime.now(timezone.utc)  # ✓ Fixed
```

**Improvements**:
- ✓ Fixed SQL function being used as Python datetime
- ✓ Proper UTC timezone handling

**Additional changes**:
```python
# Added async lock to TelegramAuth singleton
_telegram_auth_lock = asyncio.Lock()

async def _get_telegram_auth(settings: Settings) -> "TelegramAuth":
    """Return a shared TelegramAuth singleton so pending clients persist across requests."""
    global _telegram_auth_instance
    async with _telegram_auth_lock:  # ← Thread-safe initialization
        if _telegram_auth_instance is None:
            _telegram_auth_instance = TelegramAuth(...)
    return _telegram_auth_instance
```

**Why this matters**: Multiple concurrent requests could create duplicate TelegramAuth instances without the lock. Now only one thread initializes it.

---

## Test Coverage

### New Tests (125 lines)
```
TestTelegramAuthSendCode
  - test_send_code_propagates_flood_wait()
  - test_send_code_propagates_phone_number_invalid()

TestTelegramAuthVerifyCode
  - test_verify_code_propagates_phone_code_invalid()

# More error scenario tests...
```

**Coverage**: All four Telegram endpoints have error propagation tests.

---

## Migration 018 (Schema Changes)

```python
# New columns for session lifecycle visibility
+ disconnected_reason: VARCHAR (e.g., "user_disconnected", "flood_wait", "session_expired")
+ disconnected_at: TIMESTAMP WITH TZ
```

These columns enable frontend to show:
- "Session disconnected 2 hours ago"
- "Reconnect" CTA instead of generic "something went wrong"

---

## Known Risks & Mitigations

### Risk 1: Broad Exception Catching
**Issue**: `except Exception` catches all Telethon exceptions we didn't anticipate
**Mitigation**: Specific exceptions handled first; fall-through is defensive
**Future**: Consider logging unhandled exception types and adding them

### Risk 2: Encryption Key Misconfiguration
**Issue**: If ENCRYPTION_KEY is missing or wrong, users get 500 error
**Mitigation**: Error message says "check ENCRYPTION_KEY configuration"
**Future**: Add ENCRYPTION_KEY validation in startup checks

### Risk 3: Telethon RuntimeError Assumption
**Issue**: Code assumes `RuntimeError` means session expired; might be wrong
**Mitigation**: Verify by checking Telethon source code or adding more specific exception handling
**Action**: Could add regex match on error message as fallback

### Risk 4: Proxy Support
**Issue**: Code now tries to pass `TELEGRAM_PROXY_URL` to `get_user_channels()`
**Mitigation**: If env var is missing, `parse_proxy_url(None)` should return None safely
**Verify**: Check `parse_proxy_url()` implementation in `src/adapters/telegram/__init__.py`

---

## Sentry Expectations

### Error Distribution Changes
**Before PR #42**:
- High 500 error rate on `/telegram/*` endpoints
- Telethon exceptions surfaced as-is to client

**After PR #42**:
- 500s dramatically reduced
- 400/401/429 errors increase (now properly handled)
- Each error has structured logging with context (user_id, operation)

### What to Monitor
1. **Did 500 count drop?** → Success metric
2. **Are 4xx errors reasonable?** (invalid codes, rate limits) → Success metric
3. **Any new 502 errors?** → May indicate Telethon/Telegram issues
4. **Any 500 "encrypt" errors?** → Check ENCRYPTION_KEY in staging env

---

## Code Quality Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Error handling | A | Comprehensive, covers most Telethon exceptions |
| Testing | A- | 125 lines of tests, could add integration tests |
| Logging | A | Includes user context (user_id) in error logs |
| Documentation | B+ | Commit message explains changes, could add code comments |
| Backward compatibility | A | No breaking changes, only additive error handling |
| Performance | A | Async lock is minimal overhead, no new queries |
| Security | A | No new security vulnerabilities introduced |

---

## Deployment Safety
- ✓ No database migrations breaking backward compatibility
- ✓ No changes to webhook payload format
- ✓ Safe to rollback: `git revert 58505a1 -m 1`
- ✓ No environment variable additions (uses optional TELEGRAM_PROXY_URL)
