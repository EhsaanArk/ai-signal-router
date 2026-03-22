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

## ~~P2 — Template Builder: Money Management Mode Awareness~~ DONE (PR pending)

Shipped in `feature/SGM-041-mm-mode-awareness`. MM mode dropdown (V2 Forex only) in both create wizard and edit page. Stored in `risk_overrides` JSON — no DB migration. Shared `MoneyManagementSelect` component + 10 unit tests.

**What:** Ask users their SageMaster Assist's money management mode in the routing rule setup, then show/hide `balance` and `lots` fields contextually in the template builder.

**Why:** SageMaster V2 has conditional field requirements based on the Assist's money management mode:
- `balance`: only used with "Indicator provider x percent w ratio check mode"
- `lots`: only used with "Indicator provider x percent w ratio check mode" or "Indicator provider x percent w/o ratio check mode"
- Other modes ignore these fields entirely

Currently users see `balance` and `lots` with no context about when they matter. This leads to confusion and unnecessary configuration. The template builder should ask "What money management mode is your Assist using?" and conditionally show/hide fields.

**Pros:**
- Self-explanatory UX — no guesswork about which fields matter
- Prevents users from configuring fields that SageMaster ignores
- Builds on the existing template builder field metadata system (platforms, groups, required flags)

**Cons:**
- Requires storing the money management mode per routing rule (new DB column or template metadata)
- SageMaster may add new modes in the future — needs to be extensible
- Users may not know which mode they're using without checking SageMaster

**Context:**
- Template builder already has `platforms`, `v2Only`, `required`, and `group` metadata on `KNOWN_FIELDS`
- Could add a `moneyManagementMode` prop to `TemplateBuilder` that controls visibility of balance/lots
- The mode options would be: "Default (ignore balance/lots)", "Indicator provider x percent w ratio check mode" (needs balance + lots), "Indicator provider x percent w/o ratio check mode" (needs lots only)
- Consider showing this as a dropdown in the routing rule form (V2 only), with a tooltip linking to SageMaster's docs

**Effort:** M (human) → S (CC)
**Priority:** P2
**Depends on:** Template builder field validation (PR #72, shipped)
**Added:** 2026-03-19 (live testing session)

---

## ~~P2 — Add Missing SageMaster Forex Action Types to Pipeline~~ DONE

All 4 actions (close_all, close_all_stop, start_assist, stop_assist) implemented in models.py, parser.py, mapper.py, and frontend action-definitions.ts. Verified 2026-03-22.

**What:** Add support for `close_all_orders_at_market_price`, `close_all_orders_at_market_price_and_stop_assist`, `start_assist`, and `stop_assist` actions.

**Why:** SageMaster V1 and V2 both support these actions but our pipeline doesn't recognize them. If a signal provider sends "close all" or "stop strategy", we'd ignore it. Verified against official SageMaster webhook spec (2026-03-19).

**Pros:**
- Complete parity with SageMaster's webhook spec (both V1 and V2)
- Users can forward more signal types
- `close_all` is commonly used by signal providers ("close all trades")

**Cons:**
- Need to update parser prompt to recognize these intents
- Need to update `SignalAction` enum and mapper
- "close all" is destructive — needs careful handling (maybe require confirmation in enabled_actions)

**Context:**
- Full spec documented in `docs/WEBHOOK_PAYLOADS.md`
- Gap analysis (2026-03-19): 4 actions missing from pipeline

**Implementation plan:**

1. `src/core/models.py` — Add to `SignalAction` enum:
   - `close_all = "close_all_orders_at_market_price"` (no symbol needed)
   - `close_all_stop = "close_all_orders_at_market_price_and_stop_assist"` (no symbol needed)
   - `start_assist = "start_assist"` (no symbol needed)
   - `stop_assist = "stop_assist"` (no symbol needed)

2. `src/core/mapper.py` — Update `_signal_action()` to map parser actions:
   - `"close_all"` → `SignalAction.close_all`
   - `"close_all_stop"` → `SignalAction.close_all_stop`
   - `"start_assist"` → `SignalAction.start_assist`
   - `"stop_assist"` → `SignalAction.stop_assist`
   - These actions don't need symbol — update `_strip_entry_fields` and management field injection

3. `src/adapters/openai/parser.py` — Update system prompt to recognize:
   - "close all trades" / "close everything" → `action: "close_all"`
   - "stop the bot" / "pause strategy" → `action: "stop_assist"`
   - "start the bot" / "resume" → `action: "start_assist"`

4. `frontend/src/lib/action-definitions.ts` — Add to enabled_actions UI:
   - `close_all`, `close_all_stop`, `start_assist`, `stop_assist`

5. `src/core/models.py` — Update `WebhookPayloadV2` validator:
   - These actions don't require `symbol` or `source` — skip validation for them

**Effort:** M (human) → S (CC)
**Priority:** P2
**Depends on:** Nothing
**Added:** 2026-03-19 (full spec review)

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

---

## P2 — Remove legacy token fallback after migration window

**What:** Remove the backward-compatibility code in `_find_valid_token_row()` that scans rows with `token_lookup_hash IS NULL` via bcrypt. Once all pre-migration tokens have expired, this path is dead code.

**Why:** The legacy fallback scans up to 500 rows with bcrypt (~100ms each), creating a potential DoS surface. After migration 023 deploys and all old tokens expire (max 24h for email verification, 1h for password reset), no rows will have NULL `token_lookup_hash`. The fallback adds complexity for zero value.

**Pros:**
- Removes dead code and potential DoS surface
- Simplifies `_find_valid_token_row()` to a single O(1) hash lookup
- Reduces bcrypt CPU usage on token endpoints

**Cons:**
- If somehow old tokens persist beyond 24h (e.g., DB snapshot restore), removal would break them

**Context:**
- PR #96 adds `token_lookup_hash` column + migration 023 + the legacy fallback
- New tokens always get a hash. Legacy tokens expire within 24h.
- Safe to remove after PR #96 has been deployed to production for 48+ hours
- Files to modify: `src/api/routes.py` (remove legacy branch from `_find_valid_token_row`)

**Effort:** S (human) → S (CC)
**Priority:** P2
**Depends on:** PR #96 deployed to production for 48+ hours
**Added:** 2026-03-20 (eng review of PR #96)

---

## P2 — E2E test pipeline with SageMaster staging verification

**What:** A dedicated test route that sends a synthetic signal through the full pipeline to a SageMaster staging webhook, then headlessly logs into SageMaster and verifies the trade landed. Proves the entire pipeline works end-to-end (parser → mapper → webhook → SageMaster accepts it).

**Why:** The admin test-dispatch endpoint was hardened to sandbox-only (2026-03-21) — it can no longer dispatch to real webhooks. This is correct for security, but means there's no way to verify that SageMaster actually accepts our payloads. A dedicated E2E test pipeline with a staging webhook fills this gap without risking real user trades.

**Pros:**
- Full pipeline verification: proves SageMaster accepts our payload format
- Catches integration issues that sandbox previews can't (auth failures, payload rejection, API changes)
- Can be triggered as a post-deploy smoke test by the railway-ops agent

**Cons:**
- Requires a dedicated SageMaster staging/test account and webhook URL
- Headless browser verification adds infrastructure complexity (Playwright, SageMaster login)
- Touches protected pipeline files (needs its own eng review)
- SageMaster staging availability is outside our control

**Context:**
- The admin test-dispatch endpoint was converted to sandbox-only in the security hardening PR (2026-03-21). Previously it could dispatch to any user's webhook — a security gap for a trading platform.
- This TODO is the "do it properly" follow-up: a dedicated test pipeline with a known staging webhook, not reusing user webhooks.
- Related to the existing "Pipeline dry-run smoke test" TODO but goes further — that one skips dispatch, this one actually dispatches to a test webhook and verifies receipt.
- Needs: SageMaster staging credentials, a test Assist configured in SageMaster, Playwright for headless verification.

**Effort:** L (human) → M (CC)
**Priority:** P2
**Depends on:** SageMaster staging account setup (manual step)
**Added:** 2026-03-21 (eng review of test-dispatch security hardening)

---

## P3 — Signal history stats in Command Reference drawer

**What:** Add a small section at the bottom of the Command Reference drawer showing signal processing stats for the last 7 days: total signals processed, matched, ignored (with breakdown by reason: keyword blacklist, disabled action, parse failure).

**Why:** Users want confidence that their route is working. Currently they have no visibility into signal processing without checking signal logs. A quick stats summary in the drawer they're already looking at builds trust and surfaces issues early.

**Pros:**
- Builds user confidence ("23 signals processed, 21 matched")
- Surfaces issues proactively (high ignore rate = misconfiguration)
- Natural fit in the Command Reference drawer (context-appropriate)

**Cons:**
- Requires a new API endpoint to aggregate `signal_logs` per routing rule
- Signal log queries could be slow for high-volume routes without proper indexing
- Adds backend scope to what is otherwise a frontend-only feature

**Context:**
- The Command Reference drawer (see `docs/designs/SIGNAL-COMMAND-REFERENCE-PANEL.md`) shows command definitions and toggles. This would add a data-driven section at the bottom.
- Query: `SELECT status, COUNT(*) FROM signal_logs WHERE routing_rule_id = ? AND created_at > NOW() - INTERVAL '7 days' GROUP BY status`
- Consider caching the result in Redis with a 5-minute TTL to avoid repeated DB queries

**Effort:** M (human) → S (CC)
**Priority:** P3
**Depends on:** Command Reference drawer (Signal Command Reference Panel feature)
**Added:** 2026-03-21 (CEO plan review)
