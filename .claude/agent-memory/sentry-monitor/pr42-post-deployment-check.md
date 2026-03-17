---
name: PR #42 Post-Deployment Status
description: Sentry monitoring checklist after PR #42 merged to staging (2026-03-17)
type: project
---

## PR #42 Merge Summary
**Commit**: 58505a1 (Tue Mar 17 20:06:09 2026)
**Branch**: staging (auto-deployed to Railway staging)
**Status**: DEPLOYED ✓

## What Changed
PR #42 added comprehensive error handling to all Telegram auth endpoints to eliminate 500 errors and return proper HTTP status codes:

### Endpoints Fixed
1. **POST /telegram/send-code**
   - PhoneNumberInvalidError → 400 Bad Request
   - FloodWaitError → 429 Too Many Requests (with Retry-After header)
   - Generic exceptions → 502 Bad Gateway

2. **POST /telegram/verify-code**
   - PhoneCodeInvalidError → 400 Bad Request
   - PhoneCodeExpiredError → 400 Bad Request
   - FloodWaitError → 429 Too Many Requests (with Retry-After header)
   - Encryption failures → 500 Internal Server Error (with helpful message)
   - Generic exceptions → 502 Bad Gateway

3. **GET /telegram/channels**
   - Session decryption failures → 400 Bad Request
   - FloodWaitError → 429 Too Many Requests (with Retry-After header)
   - Expired session → 401 Unauthorized
   - Generic exceptions → 502 Bad Gateway

4. **POST /telegram/disconnect**
   - Fixed `func.now()` usage (now uses `datetime.now(timezone.utc)`)
   - Async lock added to TelegramAuth singleton to prevent race conditions

### Test Coverage Added
- 125 new test lines in `test_telegram.py`
- Error propagation tests for Telethon exceptions
- Flood wait handling tests
- Phone number validation tests

## Expected Behavior Post-Deploy
All Telegram endpoints should now:
- Return semantic HTTP status codes instead of 500s
- Log exceptions with context (user ID, operation)
- Return user-friendly error messages
- Include Retry-After headers for rate limits

## Sentry Monitoring Checklist

### NEW Issues to Watch For (Next 24-48 Hours)
- [ ] Any new 400/401/429 errors in Telegram endpoints (expected, but verify they're client errors not bugs)
- [ ] Any 502 errors persisting (indicates Telethon/external service issues)
- [ ] Session decryption failures (500 on /telegram/channels)
- [ ] TelegramAuth singleton race conditions (now protected by async lock)

### REGRESSIONS to Verify Absent
- [ ] `'User' has no attribute 'title'` (fixed in PR #40, should remain fixed)
- [ ] "not authorised" retry loops (fixed in PR #40)
- [ ] RuntimeError "not authorised" (fixed in PR #40)
- [ ] InterfaceError connection closed (should still monitor for Neon pool issues)

### Questions for Investigation
1. Are we seeing any FloodWaitError patterns (users getting rate-limited)?
2. Are phone number validation errors legitimate client mistakes or platform issues?
3. Are any encryption key issues showing up (400 errors on /telegram/channels)?

## Status as of 2026-03-17 20:15 UTC
Deployment pending verification via Railway staging logs and Sentry dashboard.
