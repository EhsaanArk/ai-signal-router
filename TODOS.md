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

## ~~P1 — Zero-downtime deploy: prevent session invalidation on redeploy~~ DONE (staging verified)

**What:** Prevent Railway redeploys from invalidating users' Telegram sessions. Currently, when Railway replaces the Listener container, the old and new instances briefly overlap — both try to use the same MTProto session simultaneously, causing Telegram to throw `AuthKeyDuplicatedError` and permanently invalidate the session. Affected users must re-authenticate from scratch.

**Why:** Every staging/production deploy risks disconnecting users from their Telegram accounts. On the 2026-03-18 deploy (PR #52), 4 out of 7 users lost their sessions. This is unacceptable for a trading signal copier — users miss trades and must manually reconnect. Our deploys should never break user connections.

**Pros:**
- Users never lose their Telegram connection due to our deploys
- Builds trust — "it just works" even during maintenance
- Eliminates support burden of telling users to reconnect after every deploy

**Cons:**
- Requires understanding Railway's container replacement behavior
- May need coordination between old/new container (graceful handoff)
- Some approaches add infrastructure complexity (e.g., leader election, session locking)

**Context:**
- Root cause: Railway spins up the new container before killing the old one (rolling deploy). Both containers connect to Telegram using the same session string, triggering Telegram's `AuthKeyDuplicatedError` (duplicate auth key on two IPs).
- Possible solutions:
  1. **Graceful shutdown with delay**: On SIGTERM, immediately disconnect all Telethon clients (release sessions) BEFORE the new container starts connecting. Add a startup delay in the new container to ensure the old one has fully released.
  2. **Session locking via Redis**: Use a distributed lock (Redis `SET NX EX`) per user session. Old container releases lock on shutdown, new container waits for lock before connecting. Prevents two containers from using the same session simultaneously.
  3. **Railway deploy strategy**: Configure Railway to use "recreate" instead of "rolling" deploy strategy for the Listener service — kill old before starting new. Trades a few seconds of downtime for zero session conflicts (backfill covers the gap).
  4. **Startup coordination**: New container checks if old container is still running (via Redis heartbeat) and waits before connecting Telegram clients.
- The backfill mechanism (PR #49) already handles signal gaps during the restart window, so a brief downtime between old-stop and new-start is acceptable.
- Solution 3 (recreate strategy) is likely the simplest and most reliable — investigate Railway's deploy configuration options first.

**Effort:** S-M (human) → S (CC) — depending on chosen approach
**Priority:** P1 — every deploy is a risk until this is fixed
**Depends on:** Nothing — can be built independently
**Added:** 2026-03-18 (post-deploy observation, PR #52)

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

## ~~P2 — Sentry heartbeat metrics for listener health~~ DONE (PR #52)

Shipped in PR #52. Sentry breadcrumbs added to `_heartbeat()` with category `telegram.heartbeat`, including connected/total listener counts and channel count.

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

---

## P2 — Pipeline dry-run smoke test for post-deploy verification

**What:** Add a `dry_run` flag to the signal workflow so a synthetic test signal can be sent through QStash → workflow → parser → mapper without dispatching to the actual webhook.

**Why:** Catches silent pipeline breaks post-deploy — parser regressions, QStash auth issues, mapper errors. Currently Sentry only catches errors if real signals happen to arrive. The deploy-health endpoint (PR #62) verifies session preservation but not pipeline health.

**Pros:**
- End-to-end pipeline verification in seconds
- Can be triggered by the railway-ops agent as a post-deploy step
- Catches regressions that are invisible until a real signal arrives

**Cons:**
- Touches protected pipeline files (workflow.py, mapper.py)
- Needs a test fixture signal and careful isolation so dry-run signals never reach real webhooks
- Risk of test signals leaking to production if dry_run flag is buggy

**Context:**
- Deferred from the post-deploy verification plan (CEO review 2026-03-19) because it modifies the signal pipeline (protected files per CLAUDE.md). Should be its own PR with eng review.
- The deploy-health endpoint (`/health/deploy`) provides the infrastructure to report results.
- Implementation: add `dry_run: bool = False` param to workflow steps, skip `dispatcher.dispatch()` when true, log result as `status=dry_run`.

**Effort:** M (human) → S (CC)
**Priority:** P2
**Depends on:** Nothing — deploy-health endpoint is already merged
**Added:** 2026-03-19 (CEO plan review)

---

## P3 — Admin dashboard deploy history widget

**What:** Add a "Last Deploy" card to the admin dashboard showing deploy timestamp, before/after session counts, sessions lost, and pipeline status.

**Why:** Visual deploy history accessible without terminal. Makes deploy impact visible to non-technical stakeholders.

**Pros:**
- Reuses data from the `/health/deploy` endpoint
- Quick frontend-only addition
- Historical record of deploy safety

**Cons:**
- Frontend code to maintain
- Low value until multiple team members are deploying

**Context:**
- The data source (`/health/deploy` endpoint) exists after PR #62.
- This is purely a frontend consumer — fetch the endpoint and render a card.
- Could show last 5 deploys if snapshots are stored in DB (currently Redis with 10min TTL).

**Effort:** S-M (human) → S (CC)
**Priority:** P3
**Depends on:** Deploy-health endpoint (PR #62)
**Added:** 2026-03-19 (CEO plan review)
