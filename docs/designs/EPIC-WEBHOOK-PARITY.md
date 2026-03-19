# Epic: SageMaster Webhook Parity & Smart Configuration

**Created:** 2026-03-19
**Status:** PLANNED
**Owner:** Ehsaan
**Goal:** 100% SageMaster action coverage + self-configuring template builder that eliminates guesswork

## Background

Live testing on 2026-03-19 revealed several gaps between our pipeline and SageMaster's full webhook spec. The template builder also lacks context about SageMaster's Assist configuration, forcing users to guess which fields matter. This epic closes those gaps.

## Current State

```
PIPELINE ACTION COVERAGE (Forex V1/V2):
  ✅ start_long_market_deal          ✅ start_short_market_deal
  ✅ start_long_limit_deal           ✅ start_short_limit_deal
  ✅ close_order_at_market_price     ❌ close_all_orders_at_market_price
  ❌ close_all_orders_at_market_price_and_stop_assist
  ❌ start_assist                    ❌ stop_assist
  ✅ partially_close_by_lot          ✅ partially_close_by_percentage
  ✅ move_sl_to_breakeven

  Coverage: 8/12 actions (67%)

TEMPLATE BUILDER UX:
  ✅ Required field badges (PR #72)
  ✅ Platform-aware filtering (PR #72)
  ✅ V1/V2-aware visibility (PR #72)
  ✅ Field description tooltips (PR #72)
  ✅ Pre-save validation (PR #72)
  ✅ V2 TP/SL help banner (PR #74)
  ✅ Empty field stripping in mapper (PR #75)
  ❌ Money management mode awareness
  ❌ Contextual field help based on Assist config
```

## Sprint 1: Full Action Coverage (SGM-040)

**Goal:** 100% SageMaster action parity
**Effort:** S (human: ~4hrs / CC: ~20min)
**Risk:** Low — additive, doesn't change existing flows
**Branch:** `feature/SGM-040-missing-actions`

### New Actions

| Action | Type String | Symbol Required? | Notes |
|--------|------------|-----------------|-------|
| Close ALL positions | `close_all_orders_at_market_price` | No | Closes every open trade |
| Close ALL + stop | `close_all_orders_at_market_price_and_stop_assist` | No | Closes all + stops the Assist |
| Start Assist | `start_assist` | No | Resumes a stopped Assist |
| Stop Assist | `stop_assist` | No | Pauses the Assist (no new trades) |

### Files to Modify

**1. `src/core/models.py`** — Add to `SignalAction` enum:
```python
close_all = "close_all_orders_at_market_price"
close_all_stop = "close_all_orders_at_market_price_and_stop_assist"
start_assist_action = "start_assist"
stop_assist_action = "stop_assist"
```

Update `WebhookPayloadV2._check_required_fields_per_action`:
- These 4 actions don't require `symbol` or `source` — skip validation for them

**2. `src/core/mapper.py`** — Update `_signal_action()`:
```python
if action == "close_all": return SignalAction.close_all
if action == "close_all_stop": return SignalAction.close_all_stop
if action == "start_assist": return SignalAction.start_assist_action
if action == "stop_assist": return SignalAction.stop_assist_action
```

Update non-entry handling: these actions need core fields only (type, assistId, source, date) — no symbol, no management fields.

**3. `src/adapters/openai/parser.py`** — Update system prompt to recognize:
- "close all trades" / "close everything" / "flatten" → `action: "close_all"`
- "stop the bot" / "pause" / "disable" → `action: "stop_assist"`
- "start the bot" / "resume" / "enable" → `action: "start_assist"`
- "close all and stop" → `action: "close_all_stop"`

**4. `frontend/src/lib/action-definitions.ts`** — Add to enabled_actions UI:
- `close_all`: "Close All Positions — closes every open trade for this symbol"
- `close_all_stop`: "Close All & Stop — closes all trades and pauses the Assist"
- `start_assist`: "Start Assist — resumes a paused Assist"
- `stop_assist`: "Stop Assist — pauses the Assist (no new trades)"

**5. Tests:**
- `tests/test_mapper.py` — 4 new tests for action mapping
- `tests/test_webhook_payloads.py` — 4 new tests for payload construction
- `tests/test_openai_parser.py` — fixture signals for "close all", "stop bot", etc.

### Acceptance Criteria
- [ ] "Close all trades" in Telegram → `close_all_orders_at_market_price` webhook dispatched
- [ ] "Stop the bot" in Telegram → `stop_assist` webhook dispatched
- [ ] Users can enable/disable these actions per routing rule in the UI
- [ ] All existing tests still pass

---

## Sprint 2: Money Management Mode UX (SGM-041)

**Goal:** Template builder asks user's Assist configuration → shows only relevant fields
**Effort:** S-M (human: ~1day / CC: ~25min)
**Risk:** Low — frontend-only, no pipeline changes
**Branch:** `feature/SGM-041-mm-mode-awareness`

### Problem

SageMaster V2 has conditional field requirements based on the Assist's money management mode:
- `balance`: only used with "Indicator provider x percent w ratio check mode"
- `lots`: only used with "Indicator provider x percent w ratio check mode" or "w/o ratio"
- Other modes ignore these fields entirely

Users currently see both fields with no context. They configure values that SageMaster ignores.

### Design

Add a dropdown to the routing rule form (V2 Forex only):

```
┌─────────────────────────────────────────────────┐
│ SageMaster Money Management Mode                │
│ ┌─────────────────────────────────────────────┐ │
│ │ ▼ Select your Assist's money management...  │ │
│ └─────────────────────────────────────────────┘ │
│ ℹ️ Found in your SageMaster Assist settings     │
│                                                 │
│ Options:                                        │
│ • Default (fixed lot from strategy)             │
│ • Indicator % with ratio check (needs balance   │
│   + lots)                                       │
│ • Indicator % without ratio check (needs lots)  │
│ • I'm not sure (show all fields)                │
└─────────────────────────────────────────────────┘
```

Based on selection:
- **Default** → hide `balance` and `lots` from builder
- **With ratio** → show both `balance` and `lots` as required
- **Without ratio** → show `lots` as required, hide `balance`
- **Not sure** → show all (current behavior)

### Files to Modify

1. `frontend/src/components/forms/template-builder.tsx` — Accept `moneyManagementMode` prop, filter balance/lots visibility
2. `frontend/src/pages/routing-rules-edit.tsx` — Add MM mode dropdown (V2 forex only)
3. `frontend/src/components/forms/step-set-destination.tsx` — Same dropdown for create wizard
4. `frontend/src/types/api.ts` — Add `money_management_mode` to RoutingRuleCreate/Update
5. `src/api/routes.py` — Accept and store `money_management_mode` (nullable string column, or store in risk_overrides JSON)

### Storage Decision

**Option A:** New nullable column `money_management_mode` on `routing_rules` table
**Option B:** Store in existing `risk_overrides` JSON field (no migration needed)

Recommend **Option B** — no migration, the value is only used by the frontend to configure the builder. The backend doesn't need it for dispatch.

### Acceptance Criteria
- [ ] V2 Forex route creation shows MM mode dropdown
- [ ] Selecting "Default" hides balance/lots from builder
- [ ] Selecting "with ratio" shows balance + lots as required
- [ ] Edit page preserves the selection
- [ ] V1 and Crypto routes don't show the dropdown

---

## Sprint 3: Per-Rule Staleness Override (SGM-042)

**Goal:** Each routing rule can set its own signal freshness threshold for backfill
**Effort:** M (human: ~2days / CC: ~30min)
**Risk:** Low-Med — DB migration + backfill logic change
**Branch:** `feature/SGM-042-per-rule-staleness`

### Problem

Backfill uses a global `BACKFILL_MAX_AGE_SECONDS` (60s). But different channels have different needs:
- Scalping channel: 30s (signals go stale fast)
- Swing trading: 300s (signals valid for minutes)
- News channel: 10s (extremely time-sensitive)

### Design

1. **DB Migration:** Add `max_signal_delay_seconds` nullable int column to `routing_rules`
2. **Backend:** In backfill, query the *minimum* `max_signal_delay_seconds` across all rules for a given channel. Fall back to global default when null.
3. **Frontend:** Add optional field in Advanced Settings of routing rule form

```
┌─────────────────────────────────────────────────┐
│ ▼ Advanced Settings                             │
│                                                 │
│ Signal Freshness (optional)                     │
│ ┌─────────────┐ seconds                         │
│ │ 60          │                                 │
│ └─────────────┘                                 │
│ ℹ️ Max age for backfilled signals after a        │
│   reconnect. Signals older than this are         │
│   ignored. Default: 60s                          │
└─────────────────────────────────────────────────┘
```

### Files to Modify

1. `alembic/versions/021_add_staleness_override.py` — Migration
2. `src/adapters/db/models.py` — Add column to RoutingRuleModel
3. `src/adapters/telegram/backfill.py` — Use per-rule threshold
4. `src/api/routes.py` — Accept in create/update
5. `frontend/src/types/api.ts` — Add field
6. `frontend/src/pages/routing-rules-edit.tsx` — Add to Advanced Settings
7. `frontend/src/components/forms/step-set-destination.tsx` — Add to wizard

### Acceptance Criteria
- [ ] Each rule can set its own freshness threshold
- [ ] Backfill uses the minimum threshold across rules for a channel
- [ ] Null = use global default (60s)
- [ ] Frontend shows the setting in Advanced Settings

---

## NOT in Scope (this epic)

- **Signal Marketplace** — separate epic, P1 when marketplace work begins
- **Modify TP/SL after trade open** — SageMaster doesn't support this action
- **Crypto V2** — SageMaster Crypto has no V1/V2 split
- **V1/V2 unification** — live testing proved this isn't possible (Assist Trigger Condition)

---

## Timeline

```
Week 1:  Sprint 1 — Missing actions (SGM-040)        ~20min CC
Week 2:  Sprint 2 — MM mode UX (SGM-041)             ~25min CC
Week 3:  Sprint 3 — Staleness override (SGM-042)     ~30min CC
         ────────────────────────────────────────
Total:   ~75 min CC time across 3 weeks
Human equivalent: ~2 weeks full-time
```
