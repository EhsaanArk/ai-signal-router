# TODOS

## ~~P2 — Signal backfill with staleness filter on listener reconnect~~ DONE (PR pending)

Built in `feature/SGM-030-signal-backfill-on-reconnect`. Includes dedup check in workflow.py (skips `success` + `ignored`), staleness filter with DB logging (60s default via `BACKFILL_MAX_AGE_SECONDS`), and 12 tests.

**What:** When the listener process restarts (deploy, crash), fetch the last N messages from each monitored channel via Telegram's message history API and process any that were missed — but only if they're within a configurable time tolerance.

**Why:** During a Railway deploy, the listener restarts and all Telegram connections drop. Signals sent during the ~10-30 second restart window are silently lost. For trading signals, a missed entry could mean a missed trade. However, stale signals (e.g., a 2-minute-old XAUUSD entry) are potentially harmful — acting on stale trading signals is worse than missing them.

**Pros:**
- Eliminates the deploy gap where signals are silently lost
- Time tolerance prevents stale signals from being routed (configurable per routing rule or global)
- Deduplication via `signal_logs.message_id` prevents double-processing

**Cons:**
- Adds complexity to the reconnect path
- Telegram message history API calls could trigger flood-wait
- Need to handle the edge case where a channel has been deleted during the restart

**Context:**
- `RawSignal.timestamp` already captures UTC time — compare against Telegram message `date` field
- Staleness threshold should be configurable: global default (e.g., 60s) with per-routing-rule override (`max_signal_delay_seconds`)
- On reconnect, for each monitored channel: fetch last 10 messages, filter by `message.date > (now - max_delay)`, deduplicate against `signal_logs`, enqueue survivors
- Stale signals should be logged as `status=ignored, error_message="stale_signal: Xsec delay exceeds threshold"`

**Effort:** M
**Priority:** P2
**Depends on:** Nothing — can be built independently
**Added:** 2026-03-17 (CEO plan review)

---

## P3 — Per-routing-rule staleness override for backfill

**What:** Allow each routing rule to set its own `max_signal_delay_seconds`, overriding the global `BACKFILL_MAX_AGE_SECONDS` (60s default).

**Why:** Different channels have different signal freshness requirements. A scalping channel's signals go stale in 30 seconds; a swing trading channel's signals might be valid for 5 minutes. The current global threshold is a one-size-fits-all compromise.

**Pros:**
- More accurate staleness filtering per use case
- Prevents both missed-valid-signals and acted-on-stale-signals

**Cons:**
- Requires a DB migration to add `max_signal_delay_seconds` nullable int column to `routing_rules`
- Frontend UI needed to configure it per routing rule
- Adds complexity to the backfill filter loop (must query routing rules per channel)

**Context:**
- Backfill currently uses `BACKFILL_MAX_AGE_SECONDS` env var (default 60s) globally
- To implement: add nullable int column to `routing_rules`, query during backfill, fall back to global default when null
- The backfill method iterates by channel, not by routing rule — would need to query the *minimum* `max_signal_delay_seconds` across all rules for a given channel

**Effort:** M
**Priority:** P3
**Depends on:** Backfill feature (SGM-030) must be merged first
**Added:** 2026-03-18 (eng review)

---

## P2 — Sentry heartbeat metrics for listener health

**What:** Add Sentry breadcrumbs and structured context to the heartbeat loop so listener health is visible in Sentry dashboards.

**Why:** Currently the heartbeat only logs to stdout. If a user reports "my signals stopped working", the only way to investigate is to check Railway logs. Sentry breadcrumbs would make this visible in the error context trail.

**Pros:**
- Listener health visible in Sentry without log diving
- User-scoped Sentry context already exists (`_capture_user_exception`)

**Cons:**
- Sentry breadcrumb volume could be high (every 30s × N users)

**Context:**
- Use `sentry_sdk.add_breadcrumb()` in `_heartbeat()` with category="telegram.heartbeat"
- Set Sentry context tags: `telegram.listeners.total`, `telegram.listeners.connected`
- Consider: only emit breadcrumbs when state changes (not every 30s)

**Effort:** S
**Priority:** P2
**Depends on:** Nothing
**Added:** 2026-03-17 (CEO plan review)
