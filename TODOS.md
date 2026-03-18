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

---

## P1 — Signal Marketplace: Master Listener Architecture

**What:** Run a dedicated Sage Radar Telegram account that monitors marketplace-listed channels on behalf of all marketplace subscribers, eliminating the dependency on community members being connected.

**Why:** The marketplace V1 (planned) piggybacks on existing user connections — if no community member is connected to a marketplace channel, subscribers receive no signals. A master listener guarantees 100% signal uptime for marketplace providers.

**Pros:**
- 100% signal delivery uptime for marketplace subscribers
- No dependency on community members staying connected
- Enables the marketplace to function as a truly self-contained signal delivery system

**Cons:**
- Requires a dedicated Telegram account with proxy infrastructure
- Flood-wait management for potentially hundreds of channels
- Additional Railway service (persistent listener) to operate and monitor
- Telegram ToS considerations for automated account usage at scale

**Context:**
- The marketplace plan (CEO review 2026-03-18) resolved key architecture decisions: workflow fan-out (not listener broadcast), parsed-data-only sharing (never raw TG messages), `source_type` column in signal_logs, `MARKETPLACE_ENABLED` feature flag
- Full CEO plan with competitive research stored at `~/.gstack/projects/EhsaanArk-ai-signal-router/ceo-plans/2026-03-18-signal-marketplace.md`
- Competitors: Cornix has marketplace (crypto-only, still requires TG); ZuluTrade/eToro have full self-contained marketplaces (no TG dependency)
- New DB tables designed: `marketplace_providers`, `marketplace_subscriptions`, `marketplace_consent_log`

**Effort:** L (human) → M (CC)
**Priority:** P1 (when marketplace feature work begins)
**Depends on:** Marketplace V1 (directory + analytics + routing + legal framework)
**Added:** 2026-03-18 (CEO plan review)
