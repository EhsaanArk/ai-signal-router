# Signal Command Reference Panel

**Status:** DESIGN COMPLETE
**Created:** 2026-03-21
**CEO Review:** 2026-03-21 (SELECTIVE EXPANSION)
**Owner:** Ehsaan
**Priority:** P1 — critical for user trust and self-service

## Problem

Users don't know what signal messages their routing rule understands. They can't see:
- What commands/messages are supported
- What each command does (what webhook action it triggers)
- Which commands they've enabled or disabled
- What messages are NOT supported (platform limitations)

This leads to confusion, support tickets, and wasted signals.

## Solution

A **slide-out drawer** (Sheet component) accessible from the routing rules list via kebab menu → "View Commands". Shows every supported signal type with:
- Plain-English description of what it does
- Example Telegram messages that trigger it (with copy-to-clipboard)
- Enable/disable toggles that **save inline** (no need to enter edit mode)
- Clear indication of required vs optional commands
- "Not Supported" section for known limitations
- **Test a Command** sandbox — paste a Telegram message, see what the AI parser would do
- **Command count badge** on rule cards (e.g., "8/12 active")

## Design

### Command Categories

#### Required Commands (cannot disable)
These are essential for webhook trading to function:

| Command | Example Messages | Webhook Action |
|---------|-----------------|----------------|
| Market Entry | "Buy XAUUSD", "Sell BTC/USDT" | Opens a market order |
| Limit Entry | "Buy limit EURUSD 1.0850" | Opens a limit order at price |
| Entry with TP/SL | "Buy XAUUSD SL 2300 TP 2350" | Opens trade with risk management |

#### Optional Commands (user can enable/disable)

| Command | Example Messages | Webhook Action | Default |
|---------|-----------------|----------------|---------|
| Close Position | "Close XAUUSD", "Exit trade" | Closes position at market price | ON |
| Close All Trades | "Close all trades", "Flatten" | Closes ALL open positions | ON |
| Close All + Stop | "Close all and stop" | Closes all + pauses Assist | ON |
| Partial Close | "Close 50%", "Close half" | Closes percentage of position | ON |
| Move SL to Breakeven | "Move SL to BE", "Breakeven" | Moves SL to entry price | ON |
| Breakeven with Offset | "BE -10 pips", "BE +5" | Moves SL near entry with offset | ON |
| Stop Assist | "Stop the bot", "Pause" | Pauses the Assist | OFF |
| Start Assist | "Start the bot", "Resume" | Resumes a paused Assist | OFF |

#### Not Supported (shown for clarity)

| Command | Reason |
|---------|--------|
| Modify TP on existing trade | SageMaster doesn't support this via webhook |
| Set SL to absolute price (crypto) | SageMaster crypto only supports relative SL offsets |

### Drawer Layout Wireframe

```
┌─────────────────────────────────────────┐
│ Signal Commands              [X close]  │  Sheet header (sticky)
│ Gold Scalper · SageMaster Forex         │  Rule name + destination
├─────────────────────────────────────────┤
│                                         │  ← Scrollable content area
│ REQUIRED (always active)                │  Section label, text-[11px]
│ ┌─────────────────────────────────────┐ │
│ │ ☑ Entry Long                        │ │  Disabled switch, text-xs
│ │   Open a new long/buy position      │ │  text-[10px] muted
│ │   e.g. "Buy EURUSD at market"  [⧉]  │ │  Example + copy icon
│ ├─────────────────────────────────────┤ │
│ │ ☑ Entry Short   ☑ Long (Limit)     │ │
│ │ ☑ Short (Limit)                     │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ OPTIONAL · 6/8 active                  │  Section label + inline count
│ ┌─────────────────────────────────────┐ │
│ │ 🔘 Close Position                   │ │  Active switch
│ │   Fully close an open trade         │ │
│ │   e.g. "Close all"            [⧉]   │ │
│ ├─────────────────────────────────────┤ │
│ │ ⬚ Stop Assist                       │ │  Inactive (dimmed row)
│ │   Pause the Assist...               │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ NOT SUPPORTED                           │  Section label, muted
│ ┌─────────────────────────────────────┐ │
│ │ ✗ Modify TP on existing trade       │ │  Muted, no switch
│ │   SageMaster doesn't support this   │ │
│ └─────────────────────────────────────┘ │
│                                         │
├─────────────────────────────────────────┤  ← Sticky footer (mobile)
│ Test a Command                          │
│ ┌─────────────────────────────────────┐ │
│ │ Paste a signal message...      [▶]  │ │  Input + submit
│ └─────────────────────────────────────┘ │
│ ┌─ Result ────────────────────────────┐ │  Only shown after submit
│ │ ✓ Entry Long · XAUUSD              │ │  Highlight matches action
│ │   TP: 2350 · SL: 2300              │ │  row style + primary accent
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘

Visual hierarchy:
  1. Rule identity (name + type) — always visible in sticky header
  2. Required commands — first section, disabled toggles = "we've got this"
  3. Optional commands with toggles — interactive control
  4. Not Supported — bottom, manages expectations
  5. Test a Command — sticky footer on mobile, collapsible on desktop
```

### UI Location & Pattern

- **Slide-out drawer (Sheet)** from routing rules list kebab menu → "View Commands"
- Sheet `side="right"`, ~400px width on desktop, full-screen on mobile
- Hidden for `destination_type='custom'` routes (action definitions are SageMaster-specific)
- Toggle switches save inline via existing `PUT /routing-rules/{id}` endpoint
- Optimistic UI updates with revert on failure
- Scrollable content area with sticky header (rule name) and sticky footer (test sandbox) on mobile

### Interaction States

```
FEATURE          | LOADING          | EMPTY                | ERROR                  | SUCCESS
-----------------|------------------|----------------------|------------------------|------------------
Drawer open      | Skeleton rows    | N/A (definitions     | Toast + drawer closes  | Full content
                 |                  |  always exist)       |                        |
Toggle save      | Switch stays new | —                    | Switch reverts, toast   | Silent (stays)
                 | (optimistic)     |                      | "Failed to save"       |
Parse preview    | Spinner + "Par-  | "No signal detected. | "Couldn't parse. Try   | Result card with
                 | sing signal..."  | Try 'Buy XAUUSD'"   | different wording."    | action + symbol
Parse timeout    | —                | —                    | "Parser timed out."    | —
Rate limit       | —                | —                    | "Too many tests. Wait."| —
Copy example     | —                | —                    | Toast "Failed to copy" | Toast "Copied!"
Badge            | "—" during load  | N/A                  | "—"                    | "8/12 active"
```

### Test a Command Sandbox

- Text input: "Paste a signal message to see what it does"
- Calls new `POST /parse-preview` endpoint (wraps existing GPT-4o-mini parser)
- 10-second server-side timeout
- Returns: matched action, symbol, parameters
- **Result card design:** Same visual language as action rows (`rounded-md border`). Matched action highlighted with `border-primary` left-accent. Shows action label, symbol, and parsed parameters (TP/SL if present).
- **Empty result:** Warm language — "No signal detected in this message. Try a trading command like 'Buy XAUUSD'."
- Rate limited: 10 requests/min per user
- Does NOT dispatch to any webhook, does NOT log to signal_logs
- Response must NOT expose system prompt or internal parser configuration
- **Mobile:** Pinned to bottom of drawer as sticky footer. Content scrolls above.
- Max message length: 2000 characters

### Command Count Badge

- Displayed on each rule card in the routing rules list
- **Compact pill style:** `rounded-sm border px-1.5 py-0.5 text-[10px] font-mono` (matches existing V1/V2 format badge)
- Format: `8/12` (concise, trading-terminal aesthetic — not "8/12 commands active")
- Uses `enabled_actions` array length vs `getActionsForDestination()` total
- `null` enabled_actions = shows full count (e.g., `12/12`)
- Muted color by default, no alarm styling

### Design Tokens (matching existing codebase patterns)

- **Typography:** `text-xs` labels, `text-[10px]` descriptions/examples, `text-[11px]` section headers
- **Spacing:** `space-y-2` between rows, `px-3 py-2.5` row padding, `space-y-4` between sections
- **Active row:** `border-border` + full opacity
- **Inactive row:** `border-border/50 bg-muted/30 opacity-60`
- **Not Supported row:** `text-muted-foreground`, no switch, `✗` prefix
- **Copy icon:** `h-3 w-3 text-muted-foreground hover:text-foreground` (lucide `Copy`)
- **Components:** Sheet, Switch, Tooltip, Button, Input, toast (sonner)

### Responsive Behavior

- **Desktop (md+):** Sheet slides from right, ~400px width. Test sandbox at bottom of scroll area.
- **Mobile (<md):** Sheet takes full screen. Test sandbox pinned as sticky footer. Content scrolls above. Virtual keyboard doesn't push toggle switches.
- **Touch targets:** All interactive elements min 44px touch area on mobile.

### Accessibility

- **Keyboard:** Tab through toggles in order. Enter/Space to toggle. Escape closes drawer.
- **ARIA:** Sheet `role="dialog"` with `aria-label="Signal Commands for {rule name}"`. Each section `role="group"` with `aria-label`. Switches have `aria-label="{action label}: {enabled/disabled}"`.
- **Focus management:** On open, focus moves to close button. On close, focus returns to kebab trigger.
- **Screen reader:** Not Supported section uses `aria-label="Commands not supported by this platform"`.

### Key Principles

1. **Users can't edit the signal-to-action mapping** — that's managed by the AI parser globally
2. **Users CAN enable/disable which actions their route accepts** — this already exists as `enabled_actions` in the DB
3. **Required commands can't be disabled** — entry signals are always forwarded
4. **The panel is informational + control** — shows what's possible AND lets users control what's active

## Existing Code to Reuse

- `enabled_actions` field on `routing_rules` table — already stores which actions are enabled per rule
- `frontend/src/lib/action-definitions.ts` — already has action labels and descriptions
- `frontend/src/components/forms/step-actions.tsx` — the wizard step that shows checkboxes (can be adapted)
- Parser system prompt in `parser.py` — source of truth for what messages map to what actions

## Implementation Notes

### Frontend
- New `CommandReferenceDrawer` component (Sheet-based)
- Reuses `ACTION_DEFINITIONS` from `action-definitions.ts` — no duplication
- Add `UNSUPPORTED_ACTIONS` export to `action-definitions.ts` for "Not Supported" section
- Debounce rapid toggle switches (300ms) before sending PUT
- Optimistic UI updates with revert + toast on failure
- Copy-to-clipboard via `navigator.clipboard.writeText()` with fallback
- `useParsePreview` hook for the test-command sandbox API call
- AbortController on unmount to cancel in-flight parse-preview requests
- Max message length validation on test input (2000 chars)

### Backend
- New `POST /parse-preview` endpoint in `src/api/routes.py`
  - Auth required (current user)
  - Rate limited: 10 req/min/user (use existing rate limiter pattern)
  - Accepts: `{ message: string, destination_type: string }`
  - Calls existing `parser.parse()` with the message
  - Returns: `{ action, symbol, parameters }` — stripped of internal fields
  - Does NOT dispatch, does NOT log to signal_logs
  - Does NOT expose system prompt in response
- No DB migration needed

### Existing Reuse
- `enabled_actions` field on `routing_rules` table (DB)
- `PUT /routing-rules/{id}` endpoint (toggle save)
- `GET /routing-rules/{id}` endpoint (load rule data)
- `action-definitions.ts` (all action metadata)
- `step-actions.tsx` (toggle UI patterns — extract shared component)
- `parser.py` (parse-preview wraps existing parser)

## Effort

- Human: ~1.5 weeks (with accepted expansions)
- CC: ~45 min (frontend component + parse-preview endpoint + tests)

## CEO Review Decisions (2026-03-21)

**Mode:** SELECTIVE EXPANSION
**Approach:** C — Slide-out Drawer from Rules List

| # | Expansion | Decision |
|---|-----------|----------|
| 1 | Inline save from drawer | ACCEPTED |
| 2 | Command count badge | ACCEPTED |
| 3 | Test-command sandbox (real parser API) | ACCEPTED |
| 4 | Signal history stats | DEFERRED to TODOS.md |
| 5 | Copy example to clipboard | ACCEPTED |

**Key architecture decisions:**
- Real parser API for test sandbox (not client-side heuristic) — accuracy over speed
- Hide drawer for custom destination routes — action definitions are SageMaster-specific
- Rate limit parse-preview at 10 req/min/user — prevents OpenAI token abuse
- No DB migration required — all data already exists

## Eng Review Decisions (2026-03-21)

**Issues found:** 2 (both resolved)

| # | Issue | Decision |
|---|-------|----------|
| 1 | Parse-preview needs server-side timeout (OpenAI can take 60s+) | 10-second timeout on /parse-preview endpoint |
| 2 | Action row rendering will be duplicated in drawer + wizard | Extract shared ActionRow component (DRY) |

**Additional fixes bundled:**
- Fix `isEntry` heuristic bug in `generateActionPreview()` — `start_assist` misclassified as entry action

**Implementation patterns locked in:**
- React Query `useMutation` with optimistic updates (not manual debounce) for toggle saves
- `@limiter.limit("10/minute")` decorator (existing slowapi pattern) for parse-preview
- Stub `RawSignal` with placeholder channel_id `"preview"` for parse-preview
- shadcn/ui Sheet component for drawer (standard pattern)
- `navigator.clipboard.writeText()` for copy (no fallback needed — HTTPS only)

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | CLEAR | 5 proposals, 4 accepted, 1 deferred |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 2 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAR | score: 6/10 → 8/10, 1 decision |
| Adversarial | auto | Code safety | 0 | — | — |

- **UNRESOLVED:** 0
- **VERDICT:** CEO + ENG + DESIGN CLEARED — ready to implement
