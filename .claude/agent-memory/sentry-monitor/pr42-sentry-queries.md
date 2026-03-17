---
name: PR #42 Sentry Monitoring Queries
description: Specific Sentry queries to verify PR #42 error handling deployment
type: reference
---

## Sentry Dashboard Queries for PR #42 Verification

### Setup
- **Organization**: augera
- **Project**: python-fastapi (ID: 4511049558523984)
- **Dashboard**: https://augera.sentry.io/issues/?project=4511049558523984
- **Environment filter**: `environment:staging` (since this is a staging deployment)
- **Time range**: Last 2 hours (or last 4 hours if no traffic)

---

## Query 1: Telegram Endpoints 500 Error Rate (Should DROP)

```
status:error level:500 http.url:"/telegram/*"
```

**What to check**:
- Before PR #42: Dozens of 500 errors
- After PR #42: Should drop to 0-5 over 2-4 hours
- **Red flag**: Still seeing raw 500s after deploy → rollback immediately

**Interpretation**:
- `event_count > 0` after deploy = Bug not fixed, rollback
- `event_count < 5` after deploy = Success, error handling working

---

## Query 2: Telegram 4xx Error Distribution (Should INCREASE)

```
status:error level:400,401,429 http.url:"/telegram/*"
```

**What to check**:
- Should start seeing 400/401/429 errors post-deploy
- **Good**: 5-20 events over 2 hours (normal client errors)
- **Bad**: 50+ events over 2 hours (suggests widespread validation failures)
- **Good pattern**: Mix of different error codes (400, 401, 429)

**Breakdown by status code**:
```
status:400 http.url:"/telegram/*"  # Invalid codes, corrupted sessions
status:401 http.url:"/telegram/*"  # Expired sessions
status:429 http.url:"/telegram/*"  # Rate limited (check Retry-After adoption)
status:502 http.url:"/telegram/*"  # External service errors
```

---

## Query 3: Encryption Key Issues (Should BE ZERO)

```
message:"ENCRYPTION_KEY" OR message:"encrypt"
```

**What to check**:
- Should be 0 matches
- **Red flag**: Any matches = ENCRYPTION_KEY not configured in staging
- **Action**: Check Railway staging environment variables

---

## Query 4: Session Decryption Failures (Should BE LOW)

```
message:"decrypt" OR message:"corrupted session"
```

**What to check**:
- 0-1 per hour = Normal (some users have corrupted sessions)
- 5+ per hour = Problem (suggests encryption key rotation or corruption)
- **Red flag**: 10+ per hour = Database corruption or key mismatch

---

## Query 5: FloodWaitError Rate (Indicates Telegram Load)

```
exception.typename:"FloodWaitError"
```

**What to check**:
- 0-2 per hour = Normal (occasional Telegram rate limiting)
- 5+ per hour = Telegram is rate limiting users heavily
- **Action**: Monitor if spike indicates Telegram service issues

**Inspect**:
- Check `exc.seconds` values (how long to wait?)
- Are users retrying immediately or respecting Retry-After header?

---

## Query 6: TelegramAuth Singleton Issues (Should BE ZERO)

```
message:"TelegramAuth" OR exception.typename:"RuntimeError"
```

**What to check**:
- Should be 0 race condition errors (async lock prevents them)
- **Red flag**: Multiple "TelegramAuth already initialized" errors
- **Success**: Only normal Telethon RuntimeError for expired sessions

---

## Query 7: Per-Endpoint Error Summary

### /telegram/send-code
```
http.endpoint:"/telegram/send-code"
```
**Expected after deploy**:
- Status 200: 80-90% (successful codes sent)
- Status 400: 5-10% (invalid phone numbers)
- Status 429: 0-5% (rate limited)
- Status 502: 0-2% (Telethon/Telegram service issues)
- Status 500: 0 (should be eliminated)

### /telegram/verify-code
```
http.endpoint:"/telegram/verify-code"
```
**Expected after deploy**:
- Status 200: 60-80% (successful verification)
- Status 400: 10-20% (invalid/expired codes)
- Status 429: 0-5% (rate limited)
- Status 500: 0-2% (encryption key issues only)
- Status 502: 0-2% (Telethon issues)

### /telegram/channels
```
http.endpoint:"/telegram/channels"
```
**Expected after deploy**:
- Status 200: 90-95% (channels fetched)
- Status 400: 0-2% (corrupted sessions)
- Status 401: 0-2% (expired sessions)
- Status 429: 0-2% (rate limited)
- Status 502: 0-2% (Telethon issues)

### /telegram/disconnect
```
http.endpoint:"/telegram/disconnect"
```
**Expected after deploy**:
- Status 200: 100% (no errors, func.now() is fixed)
- Status 500: 0 (should not happen)

---

## Query 8: New Exception Types (Might Need Handling)

```
exception.typename NOT IN (PhoneNumberInvalidError, FloodWaitError, PhoneCodeInvalidError, PhoneCodeExpiredError, SessionPasswordNeededError)
```

**What to check**:
- Any unexpected exception types appearing?
- **Action**: If found, add specific handling to routes.py

---

## Query 9: Rate of Requests to Telegram Endpoints

```
http.url:"/telegram/*"
```

**What to check**:
- Should see steady stream of requests (indicates users testing)
- Compare error rate percentage before/after
- **Example**: If 100 requests → 95 status 200, 5 status 400 = 5% error rate (good)

---

## Query 10: User Experience (Frontend Perspective)

```
level:error http.status_code:429 http.url:"/telegram/*"
```

**What to check**:
- Are users hitting rate limits?
- Is frontend showing friendly error message?
- **Action**: If spike, inform users Telegram has rate-limited them

---

## Monitoring Dashboard Setup (Sentry UI)

### Create Custom Dashboard
1. Go to **Sentry → Dashboards → Create Dashboard**
2. Add widgets:

**Widget 1: Telegram Endpoints Error Rate**
```
Query: http.url:"/telegram/*" status:error
Type: Time series
```

**Widget 2: Status Code Distribution**
```
Query: http.url:"/telegram/*"
Group by: http.status_code
Type: Pie chart
```

**Widget 3: Error Rate by Endpoint**
```
Query: http.url:"/telegram/*" level:error
Group by: http.endpoint
Type: Bar chart
```

**Widget 4: FloodWaitError Timeline**
```
Query: exception.typename:"FloodWaitError"
Type: Time series
```

---

## Alert Rules to Set Up

### Alert 1: 500 Errors on Telegram Endpoints (HIGH PRIORITY)
```
Condition: status:500 http.url:"/telegram/*"
Threshold: > 5 errors in 5 minutes
Action: Sentry alert + Slack notification
```

**Why**: If we see 500s, error handling failed or new exception type appeared

### Alert 2: High Error Rate (MEDIUM PRIORITY)
```
Condition: http.url:"/telegram/*" level:error
Threshold: > 30% of requests are errors
Action: Sentry alert + Slack notification
```

**Why**: Indicates widespread user issues or Telegram service outage

### Alert 3: ENCRYPTION_KEY Not Configured (HIGH PRIORITY)
```
Condition: message:"ENCRYPTION_KEY not configured"
Threshold: > 0
Action: Sentry alert + immediate investigation
```

**Why**: Blocking issue, must fix immediately

---

## Debugging Workflow

### If You See Unexpected 500s
```
1. Search: status:500 http.url:"/telegram/*"
2. Click on an error event
3. Look at:
   - Exception type (should be caught)
   - Stack trace (where did exception escape?)
   - Request context (what was the user doing?)
4. Add specific exception handling for uncaught type
5. Create new commit, push to staging, re-test
```

### If You See Encryption Failures
```
1. Search: message:"encrypt" OR message:"ENCRYPTION_KEY"
2. Check railway env vars: railway variables --environment staging
3. Verify ENCRYPTION_KEY is set: echo $ENCRYPTION_KEY | wc -c (should be 64+ chars)
4. If missing:
   - railway variables set ENCRYPTION_KEY="<new-key>" --environment staging
   - Clear error cache and re-test
```

### If You See FloodWait Spike
```
1. Search: exception.typename:"FloodWaitError"
2. Check error details for: exc.seconds (how long to wait)
3. Is it temporary (will auto-resolve) or persistent?
4. If persistent: Check Telegram service status on status.telegram.org
5. Inform users: "Telegram is rate-limiting requests, please try again later"
```

---

## Comparison Query (Before/After)

### To see the impact over time:
```
Release: 58505a1

From 2-4 hours before deploy: http.url:"/telegram/*" status:500
From 2-4 hours after deploy:  http.url:"/telegram/*" status:500

Compare counts: Should drop significantly
```

---

## Links
- **Sentry Dashboard**: https://augera.sentry.io/issues/?project=4511049558523984
- **Sentry API Docs**: https://docs.sentry.io/api/
- **Railway Staging URL**: https://ai-signal-router-staging.up.railway.app
- **Railway Logs**: Log in → Project → Deployments → View latest deploy → Logs tab
