# SageMaster Telegram Signal Copier — Complete Product Feature Document

> **Purpose**: This document provides a comprehensive, self-contained overview of every feature, technical decision, and implementation detail in the product. It is designed to be consumed by an AI product manager who needs to understand 100% of the product without reading source code.

---

## 1. Executive Summary

**SageMaster Telegram Signal Copier** is a cloud-based SaaS platform that:
1. **Intercepts** trading signals from Telegram channels via the MTProto API
2. **Parses** them using AI (GPT-4o-mini) to extract structured trading data
3. **Routes** them to one or more SageMaster trading accounts via webhook

**Core Value Proposition**: Enable traders to automatically copy signals from Telegram signal providers directly into their SageMaster trading bots — without manual intervention — with intelligent parsing, per-destination symbol mapping, and risk controls.

**Key Differentiators**:
- **Multi-destination routing**: One Telegram channel can feed N SageMaster accounts, each with independent symbol mappings and risk settings
- **AI-powered parsing**: Uses GPT-4o-mini to interpret free-form signal text (no fixed format required)
- **Real-time processing**: Signal detection to webhook dispatch in <2 seconds
- **Tiered subscription model**: Free (1 route) → Elite (15 routes)

**Current Status**: V1 MVP complete. 254+ automated test cases. Production-ready on Railway + Neon + Upstash stack.

---

## 2. Architecture Overview

### 2.1 System Design: Hybrid Serverless

```
Telegram Channel → [MTProto Listener (Railway)] → [QStash Queue]
    → [Upstash Workflow: Parse → Map → Dispatch → Log]
        → SageMaster Webhook(s)
```

- **Telegram Listener**: Persistent Railway worker (MTProto requires long-lived connection)
- **Signal Processing**: Serverless via Upstash Workflow (event-driven, auto-retry)
- **Database**: Neon Serverless PostgreSQL (scales to zero)
- **Cache**: Upstash Redis (session caching, rate limiting)
- **AI**: OpenAI API (GPT-4o-mini for signal parsing)

### 2.2 Clean Architecture (Ports & Adapters)

```
src/core/          → Business logic, Pydantic models, interfaces (NO external imports)
src/adapters/      → Telegram, OpenAI, Webhook, DB, Redis, Email implementations
src/api/           → FastAPI routes, auth, dependencies
```

`src/core/` MUST NOT import from `src/adapters/`. All external dependencies are injected via adapter interfaces.

### 2.3 Local Development Mode

When `LOCAL_MODE=true`:
- QStash bypassed; parser called directly by listener
- Upstash Redis replaced with local Redis container
- Neon replaced with local PostgreSQL
- Signal injection endpoint available at `POST /api/dev/inject-signal`

---

## 3. Subscription Tier System

### 3.1 Tier Matrix

| Feature | Free | Starter ($29/mo) | Pro ($59/mo) | Elite ($99/mo) |
|---------|:----:|:-----------------:|:------------:|:--------------:|
| **Active Routes** | 1 | 2 | 5 | 15 |
| **Telegram Channels** | Unlimited | Unlimited | Unlimited | Unlimited |
| **AI Signal Parsing** | Yes | Yes | Yes | Yes |
| **Symbol Mapping** | Yes | Yes | Yes | Yes |
| **Signal Logs** | Yes | Yes | Yes | Yes |
| **V1 Payloads** | Yes | Yes | Yes | Yes |
| **V2 Payloads (Full Signal)** | — | — | Yes | Yes |
| **Email Notifications** | — | Yes | Yes | Yes |
| **Telegram Notifications** | — | Yes | Yes | Yes |
| **Multiple TPs** | — | — | Yes | Yes |
| **Risk Overrides** | — | — | Yes | Yes |
| **Keyword Filter** | — | — | Yes | Yes |
| **Provider Commands** | — | — | — | Yes |
| **Analytics Dashboard** | — | — | — | Yes |

### 3.2 Tier Enforcement

- **Route creation**: API returns HTTP 403 if user has reached their tier's route limit
- **Frontend**: "New Route" button disabled at limit; TierGate component shows upgrade prompt
- **Dashboard**: Shows `3/5 routes` format to indicate usage vs limit
- **Settings page**: Tier comparison card with color-coded badges (Free=gray, Starter=blue, Pro=violet, Elite=amber)

### 3.3 Data Model

```python
class SubscriptionTier(str, Enum):
    FREE = "free"       # max_destinations = 1
    STARTER = "starter" # max_destinations = 2
    PRO = "pro"         # max_destinations = 5
    ELITE = "elite"     # max_destinations = 15
```

---

## 4. Feature Catalog

### 4.1 Authentication & Account Management

#### 4.1.1 User Registration
- **Endpoint**: `POST /api/v1/auth/register` (rate limit: 3/min)
- **Fields**: email (unique), password
- **Flow**: Validate email uniqueness → hash password (bcrypt) → create user with `subscription_tier=free` → issue JWT (24h expiry)
- **Frontend**: Register page with email, password, confirm password fields; Zod validation (8+ chars, passwords match)

#### 4.1.2 User Login
- **Endpoints**: `POST /api/v1/auth/login` (form-encoded), `POST /api/v1/auth/login-json` (JSON) — rate limit: 5/min
- **Flow**: Query user by email → verify bcrypt hash → issue JWT
- **Frontend**: Login page with email/password; stores JWT in localStorage; redirects to dashboard

#### 4.1.3 Session Management
- **JWT**: HS256 algorithm, 24-hour expiry, `sub` claim contains user UUID
- **Frontend**: AuthContext checks token expiry; warns 5 minutes before expiration; auto-logout on expiry with toast notification
- **Protected Routes**: All dashboard routes wrapped in ProtectedRoute component; redirects to `/login` if no valid token

#### 4.1.4 Password Reset
- **Forgot Password**: `POST /api/v1/auth/forgot-password` — always returns success (prevents email enumeration)
- **Reset Password**: `POST /api/v1/auth/reset-password` with token from email link
- **Change Password**: `POST /api/v1/auth/change-password` (authenticated) — requires current password
- **Frontend**: Forgot password page, reset password page (with token from URL), change password form in Settings

#### 4.1.5 Current User
- **Endpoint**: `GET /api/v1/auth/me` — returns user profile (id, email, tier, created_at)
- **Frontend**: AuthContext fetches on mount and exposes via `useAuth()` hook

---

### 4.2 Telegram Integration

#### 4.2.1 Telegram Authentication (3-Step Flow)

**Step 1: Send Code**
- **Endpoint**: `POST /api/v1/telegram/send-code`
- **Request**: `{ "phone_number": "+1234567890" }`
- **Response**: `{ "phone_code_hash": "abc123" }`
- **Technical**: Creates Telethon client, sends MTProto auth request, returns hash for verification
- **Frontend**: Phone input with regex validation (`/^\+\d{7,15}$/`)

**Step 2: Verify Code**
- **Endpoint**: `POST /api/v1/telegram/verify-code`
- **Request**: `{ "phone_number": "...", "code": "12345", "phone_code_hash": "...", "password": null }`
- **Response**: `{ "status": "success" }` or `{ "status": "2fa_required" }`
- **Technical**: If 2FA required, returns `2fa_required` status without completing auth
- **Frontend**: 6-8 digit code input (monospace font); auto-advances to Step 3 if 2FA needed

**Step 3: 2FA Password (Conditional)**
- **Same endpoint**: `POST /api/v1/telegram/verify-code` with `password` field populated
- **Technical**: 2FA password used immediately for auth, NEVER stored
- **On success**: Session string encrypted with AES-256-GCM and stored in `telegram_sessions` table; cached in Redis for fast reconnection

#### 4.2.2 Session Management
- **Encryption**: AES-256-GCM via Python `cryptography` library; key from `ENCRYPTION_KEY` env var
- **Storage**: `telegram_sessions.session_string_encrypted` (PostgreSQL)
- **Cache**: Upstash Redis for fast session restoration on reconnect
- **Revocation**: Toggle `is_active` flag; disconnect clears session

#### 4.2.3 Channel Discovery
- **Endpoint**: `GET /api/v1/channels`
- **Response**: Array of `{ "id": "-100...", "title": "VIP Signals", "username": "vip_signals" }`
- **Technical**: Uses Telethon to query user's subscribed channels/groups
- **Frontend**: Channel list with search filter; shows Active channels (with routes) by default; toggle to show all 100+ channels

#### 4.2.4 Connection Status
- **Endpoint**: `GET /api/v1/telegram/status`
- **Response**: `{ "connected": true, "phone_number": "+1...", "connected_at": "..." }`
- **Frontend**: StatusBadge (green "Connected" / red "Disconnected"); phone number display; connected-since date

#### 4.2.5 Disconnect
- **Endpoint**: `POST /api/v1/telegram/disconnect`
- **Frontend**: Confirmation dialog ("This will stop all signal forwarding. Your routes will remain but won't receive new signals until you reconnect.")

---

### 4.3 Routing Rules (Signal Route Configuration)

#### 4.3.1 Data Model

```python
class RoutingRule:
    id: UUID
    user_id: UUID
    source_channel_id: str           # Telegram channel ID
    source_channel_name: str         # Display name
    destination_webhook_url: str     # SageMaster webhook URL
    payload_version: "V1" | "V2"    # Signal format
    destination_type: DestinationType  # sagemaster_forex | sagemaster_crypto | custom
    rule_name: str | None            # User-defined label
    destination_label: str | None    # Account label
    symbol_mappings: dict            # {"GOLD": "XAUUSD", "BTC": "BTCUSD"}
    risk_overrides: dict             # {"lots": "0.1"}
    webhook_body_template: dict | None  # JSON template with assistId, etc.
    custom_ai_instructions: str | None  # Per-route AI parsing context
    enabled_actions: list[str] | None   # ["entry_long", "entry_short", "close", ...]
    keyword_blacklist: list[str] | None # ["demo", "paper trade"]
    is_active: bool                  # Pause/resume routing
    created_at: datetime
    updated_at: datetime
```

#### 4.3.2 Create Route (4-Step Wizard)

**Step 1: Select Channel**
- Searchable list of user's Telegram channels
- Optional route name input (e.g., "Gold Aggressive", "EURUSD Demo")
- State preserved when navigating Back/Next

**Step 2: Set Destination**
- Destination type selector: SageMaster Forex, SageMaster Crypto, Custom Webhook
- Webhook URL input with paste detection (auto-locks when account ID detected)
- Test button: sends test POST to webhook, shows success/failure status
- Signal format: V1 (strategy trigger, no price/TP/SL) or V2 (full signal with entry, TP, SL, lots)
- Webhook body template builder:
  - **Visual mode**: field picker with known SageMaster fields (assistId, symbol, etc.)
  - **JSON mode**: raw JSON textarea with syntax validation
  - **Auto-lock**: detects Assist ID → locks display showing extracted metadata
  - **Mismatch detection**: warns if template looks like wrong platform (e.g., Crypto template but Forex selected)

**Step 3: Actions**
- Toggle which signal types to forward: Entry Long, Entry Short, Close, Partial Close %, SL to Breakeven
- Entry actions always enabled (cannot be disabled, shown with tooltip)
- Lot size override input (V2 only)
- Keyword blacklist: add/remove keywords as pills; signals containing these words are ignored
- JSON preview: expandable preview showing what the webhook payload looks like for each action

**Step 4: Symbol Mappings** (Custom destinations only; skipped for SageMaster)
- Add/remove FROM → TO pairs (e.g., GOLD → XAUUSD)
- Optional step — most users don't need this

**Submission**: `POST /api/v1/routing-rules` — validates tier limit, creates rule, returns success

#### 4.3.3 Edit Route

- **Page**: `/routing-rules/{id}/edit` with breadcrumb navigation
- **All fields editable**: name, destination, URL, format, template, AI instructions, symbol mappings, enabled actions, keyword blacklist
- **Active/Paused toggle**: Switch component to pause routing without deleting
- **URL lock**: Detects account ID in URL → shows badge with extracted ID
- **Template lock**: Detects Assist ID → shows badge with extracted metadata
- **Advanced settings**: Collapsible section for custom AI instructions

#### 4.3.4 Route List

- **Page**: `/routing-rules`
- **Desktop**: Table with columns: Route, Destination, Format, Template, Created, Status, Actions
- **Mobile**: Card layout with inline action buttons
- **Actions**: Edit, Copy URL to clipboard, Delete (with confirmation dialog)
- **Status toggle**: Optimistic UI — instantly flips active/paused, rolls back on error
- **Tier gate**: Shows upgrade banner when at route limit

#### 4.3.5 Multi-Destination Routing

- One Telegram channel can have N routing rules (no UNIQUE constraint on channel_id)
- Each rule has independent: symbol mappings, risk overrides, payload version, destination type, template
- When a signal arrives, ALL active rules matching the channel are processed independently
- Each destination gets its own log entry with per-destination payload and status

---

### 4.4 Signal Processing Pipeline

#### 4.4.1 Signal Detection
- **Telegram Listener** (persistent worker): Uses Telethon async event handlers to receive new messages
- **Channel filtering**: Only processes messages from channels with active routing rules
- **Message deduplication**: Tracks `message_id` to prevent duplicate processing
- **Follow-up detection**: Identifies reply messages (e.g., "close half", "move SL to breakeven") via `reply_to_msg_id`

#### 4.4.2 AI Signal Parsing
- **Model**: GPT-4o-mini via OpenAI API
- **Input**: Raw message text + optional custom AI instructions from routing rule
- **Output**: Structured signal data:
  ```json
  {
    "symbol": "XAUUSD",
    "direction": "buy",
    "action": "entry",
    "entry_price": 2000.50,
    "stop_loss": 1990.00,
    "take_profits": [2010.00, 2020.00, 2030.00],
    "lots": 0.1,
    "is_signal": true
  }
  ```
- **Non-signal detection**: Market analysis, general chat, and non-trading messages are classified as `is_signal: false` → logged as "ignored"
- **Error handling**: If parsing fails, signal is logged as "failed" with error message

#### 4.4.3 Symbol Mapping & Risk Overrides
- **Mapper** (`src/core/mapper.py`): For each active routing rule matching the source channel:
  1. Apply symbol mappings: replace signal symbol with destination-specific symbol (e.g., GOLD → XAUUSD)
  2. Apply risk overrides: override lot size if configured
  3. Construct webhook payload based on destination type and payload version

#### 4.4.4 Webhook Dispatch
- **Dispatcher** (`src/adapters/webhook/dispatcher.py`): HTTP POST to each destination webhook URL
- **Payload construction**: V1 or V2 format based on rule's `payload_version` and `destination_type` (Forex vs Crypto)
- **Retry**: Upstash Workflow provides automatic retries for failed HTTP requests
- **Logging**: Each dispatch attempt logged with: raw message, parsed data, webhook payload, response status, error message

#### 4.4.5 Signal Logging
- **Every signal** is logged in `signal_logs` table regardless of outcome
- **Statuses**: `success` (webhook responded OK), `failed` (parsing or dispatch error), `ignored` (non-signal message)
- **Audit trail**: Raw message, parsed data, webhook payload, error message all preserved

---

### 4.5 Dashboard

#### 4.5.1 Status Overview (Stats Strip)
- **Telegram connection**: Green dot + "Connected" or red dot + "Disconnected" (animated pulse if disconnected)
- **Routes count**: `3/5 routes` format showing active vs tier limit
- **Signal count**: Total signals with color-coded breakdown: green (success), red (failed), amber (ignored)
- **Success rate**: Percentage with color coding: green (90%+), yellow (70%+), red (<70%)
- **Refresh button**: Manual refresh with spinner animation

#### 4.5.2 Routes Overview Card
- Shows each routing rule as a mini-card with: name, channel, destination type, status badge
- Only displayed if user has routes
- Click navigates to edit page

#### 4.5.3 Recent Failures Card
- Shows top 3 most recent failed signals with error messages
- Only displayed if failures exist
- Helps users quickly identify and fix issues

#### 4.5.4 Recent Signals Table
- Last 10 signals in compact table format
- Columns: time (monospace 24h), direction arrow (green ↑ / red ↓), symbol (badge), message preview, status
- Click row → navigates to full logs page
- "View all" link → `/logs`

#### 4.5.5 New User Detection
- Auto-redirects users without any signals to `/setup` onboarding wizard
- Stores `sgm_setup_complete` in localStorage to skip on revisits

---

### 4.6 Signal Logs & Monitoring

#### 4.6.1 Logs Page (`/logs`)
- **Filters**: Status pills (All, Success, Failed, Ignored) + Route dropdown (All or specific route)
- **Live mode**: Toggle enables auto-refresh every 10 seconds with pulsing indicator
- **Pagination**: 20 logs per page, Previous/Next buttons, shows "1–20 of 150" count
- **Refresh button**: Manual refresh with spinner

#### 4.6.2 Signal Logs Table
- **Columns** (responsive): Time, Direction arrow, Symbol badge, Route name, Message preview, Entry Price, Status badge
- **Mobile**: Hides Direction, Symbol, Route, Entry Price columns
- **Row styling**: Left border color matches status (emerald=success, rose=failed, amber=ignored)
- **Click row**: Opens Signal Detail Panel (right-side sheet)

#### 4.6.3 Signal Detail Panel
- **Full pipeline visualization**: Timeline showing Received → Parsed → Dispatched → Result
- **Error banner**: Red box with error message (if failed)
- **Follow-up indicator**: Blue box explaining follow-up action (if not entry)
- **Parsed signal data**: Grid of fields (Symbol, Direction, Entry, SL, TP, Lots, etc.)
- **What was sent**: JSON code block with copy button (the actual webhook payload)
- **Destination**: Account label and webhook URL
- **Raw message**: Preformatted text block with copy button (original Telegram message)

---

### 4.7 Settings

#### 4.7.1 Account Info
- Email display, member-since date, Sign Out button

#### 4.7.2 Security
- Change password form: current password, new password (8+ chars), confirm password
- Validation: passwords must match, minimum 8 characters

#### 4.7.3 Notification Preferences
- **Email notifications**: Toggle on failure (default: on), toggle on success (default: off)
- **Telegram notifications**: Requires Starter+ tier; requires connecting Telegram bot; toggles for success/failure
- **Free tier**: Shows "Upgrade to Starter" message instead of Telegram notification toggles

#### 4.7.4 Subscription Management
- Current tier badge (color-coded)
- Tier comparison grid showing all 4 tiers with feature breakdown
- "Current" label on active tier
- "Choose" buttons on other tiers (upgrade flow not yet implemented)

---

### 4.8 Setup Wizard (Onboarding)

**3-step onboarding for new users** (`/setup`):

1. **Connect Telegram**: Embedded TelegramConnectForm; auto-advances when connected; shows "Already connected" if done
2. **Create Route**: Embedded RoutingRuleWizard (same as `/routing-rules/new`); advances on completion
3. **Listening for Signals**: Animated radio icon with pulsing animation; polls every 10 seconds for first signal; auto-advances when `logStats.total > 0`
4. **Celebration Screen**: Large checkmark, "You're all set!" message, "Go to Dashboard" button

Skip link available at bottom. Sets `sgm_setup_complete` in localStorage.

---

## 5. Webhook Schemas

### 5.1 Forex Webhooks (SageMaster SFX Platform)

**Key field**: `assistId` (NOT `assetId`)

**V1 Entry (Strategy Trigger — no price/TP/SL)**:
```json
{
  "type": "start_long_market_deal",
  "assistId": "uuid-from-template",
  "source": "forex",
  "date": "{{time}}",
  "symbol": "XAUUSD"
}
```

**V2 Entry (Full Signal)**:
```json
{
  "type": "start_long_market_deal",
  "assistId": "uuid-from-template",
  "source": "forex",
  "date": "{{time}}",
  "symbol": "XAUUSD",
  "price": "{{close}}",
  "balance": 1000,
  "lots": 1,
  "takeProfits": [2020],
  "stopLoss": 2000
}
```

**Close**: `{ "type": "close_order_at_market_price", ... }`
**Partial Close**: `{ "type": "partially_close_by_percentage", "percentage": 50, ... }`
**Breakeven**: `{ "type": "move_sl_to_breakeven", ... }`

### 5.2 Crypto Webhooks (SageMaster Crypto Platform)

**Key differences**: Uses `aiAssistId` (not `assistId`), `tradeSymbol` (not `symbol`), includes `exchange` field

**Entry**:
```json
{
  "type": "start_deal",
  "aiAssistId": "uuid-from-template",
  "exchange": "binance",
  "tradeSymbol": "BTC/USDT",
  "eventSymbol": "{{ticker}}",
  "price": "{{close}}",
  "date": "{{time}}"
}
```

The mapper automatically constructs the correct payload format based on the routing rule's `destination_type`.

---

## 6. API Endpoints Reference

### 6.1 Authentication

| Method | Path | Auth | Rate Limit | Description |
|--------|------|:----:|:----------:|-------------|
| POST | `/api/v1/auth/register` | No | 3/min | Create account |
| POST | `/api/v1/auth/login` | No | 5/min | Login (form-encoded) |
| POST | `/api/v1/auth/login-json` | No | 5/min | Login (JSON) |
| GET | `/api/v1/auth/me` | Yes | — | Current user profile |
| POST | `/api/v1/auth/change-password` | Yes | — | Change password |
| POST | `/api/v1/auth/forgot-password` | No | 3/min | Request password reset email |
| POST | `/api/v1/auth/reset-password` | No | — | Reset password with token |

### 6.2 Telegram

| Method | Path | Auth | Description |
|--------|------|:----:|-------------|
| POST | `/api/v1/telegram/send-code` | Yes | Send verification code to phone |
| POST | `/api/v1/telegram/verify-code` | Yes | Verify code (+ optional 2FA password) |
| GET | `/api/v1/telegram/status` | Yes | Connection status |
| POST | `/api/v1/telegram/disconnect` | Yes | Disconnect Telegram |

### 6.3 Channels

| Method | Path | Auth | Description |
|--------|------|:----:|-------------|
| GET | `/api/v1/channels` | Yes | List subscribed Telegram channels |

### 6.4 Routing Rules

| Method | Path | Auth | Description |
|--------|------|:----:|-------------|
| GET | `/api/v1/routing-rules` | Yes | List all user's routing rules |
| GET | `/api/v1/routing-rules/{id}` | Yes | Get single rule |
| POST | `/api/v1/routing-rules` | Yes | Create rule (checks tier limit) |
| PATCH | `/api/v1/routing-rules/{id}` | Yes | Update rule fields |
| DELETE | `/api/v1/routing-rules/{id}` | Yes | Delete rule |

### 6.5 Signal Logs

| Method | Path | Auth | Description |
|--------|------|:----:|-------------|
| GET | `/api/v1/logs` | Yes | Paginated logs (query: limit, offset, status, rule_id) |
| GET | `/api/v1/logs/stats` | Yes | Aggregated stats (total, success, failed, ignored) |

### 6.6 Webhooks

| Method | Path | Auth | Description |
|--------|------|:----:|-------------|
| POST | `/api/v1/webhook/test` | Yes | Test webhook URL connectivity |

### 6.7 Notifications

| Method | Path | Auth | Description |
|--------|------|:----:|-------------|
| GET | `/api/v1/notifications/preferences` | Yes | Get notification settings |
| POST | `/api/v1/notifications/preferences` | Yes | Update notification settings |
| GET | `/api/v1/notifications/telegram-bot-link` | Yes | Get Telegram bot connection URL |

### 6.8 Workflow (Internal — QStash Only)

| Method | Path | Auth | Description |
|--------|------|:----:|-------------|
| POST | `/api/workflow/process-signal` | QStash Signature | Process signal pipeline |

### 6.9 Development (LOCAL_MODE only)

| Method | Path | Auth | Description |
|--------|------|:----:|-------------|
| POST | `/api/dev/inject-signal` | No | Inject test signal without Telegram |

---

## 7. Database Schema

### 7.1 Tables

**users**
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default gen |
| email | VARCHAR | UNIQUE, NOT NULL |
| password_hash | VARCHAR | NOT NULL |
| subscription_tier | ENUM | free/starter/pro/elite, default free |
| notification_preferences | JSONB | default {} |
| created_at | TIMESTAMP | auto |
| updated_at | TIMESTAMP | auto |

**telegram_sessions**
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users |
| phone_number | VARCHAR | NOT NULL |
| session_string_encrypted | TEXT | AES-256-GCM encrypted |
| is_active | BOOLEAN | default true |
| last_active | TIMESTAMP | nullable |
| created_at, updated_at | TIMESTAMP | auto |
| | | UNIQUE(user_id, phone_number) |
| | | INDEX idx_telegram_sessions_active |

**routing_rules**
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users |
| source_channel_id | VARCHAR | NOT NULL |
| source_channel_name | VARCHAR | nullable |
| destination_webhook_url | VARCHAR | NOT NULL |
| payload_version | VARCHAR | V1 or V2 |
| destination_type | VARCHAR | sagemaster_forex/sagemaster_crypto/custom |
| rule_name | VARCHAR | nullable |
| destination_label | VARCHAR | nullable |
| symbol_mappings | JSONB | default {} |
| risk_overrides | JSONB | default {} |
| webhook_body_template | JSONB | nullable |
| custom_ai_instructions | TEXT | nullable |
| enabled_actions | ARRAY(VARCHAR) | nullable |
| keyword_blacklist | ARRAY(VARCHAR) | nullable |
| is_active | BOOLEAN | default true |
| created_at, updated_at | TIMESTAMP | auto |
| | | INDEX idx_routing_rules_lookup (user_id, source_channel_id) WHERE is_active |

**signal_logs**
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users |
| routing_rule_id | UUID | FK → routing_rules, nullable |
| raw_message | TEXT | original Telegram message |
| parsed_data | JSONB | AI-extracted signal data |
| webhook_payload | JSONB | actual payload sent |
| status | VARCHAR | success/failed/ignored |
| error_message | TEXT | nullable |
| message_id | VARCHAR | Telegram message ID |
| channel_id | VARCHAR | source channel |
| reply_to_msg_id | VARCHAR | for follow-up signals |
| processed_at | TIMESTAMP | auto |
| | | INDEX idx_signal_logs_user_date (user_id, processed_at DESC) |

**password_reset_tokens**
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users |
| token | VARCHAR | UNIQUE |
| expires_at | TIMESTAMP | |
| used | BOOLEAN | default false |

### 7.2 Migrations (Alembic — 13 versions)

1. Initial schema (users, telegram_sessions, routing_rules, signal_logs)
2. Password reset tokens
3. Add `webhook_body_template` to routing_rules
4. Add message tracking (`message_id`, `channel_id`) to signal_logs
5. Change `webhook_body_template` column type to JSONB
6. Add `notification_preferences` to users
7. Add missing indexes for performance
8. Add `rule_name` and `destination_label` to routing_rules
9. Add `destination_type` and `custom_ai_instructions` to routing_rules
10. Add `reply_to_msg_id` to signal_logs
11. Add `enabled_actions` to routing_rules
12. Add Telegram notification preferences support
13. Add `keyword_blacklist` to routing_rules

---

## 8. Security

### 8.1 Data at Rest
- **Telegram sessions**: AES-256-GCM encrypted, key from `ENCRYPTION_KEY` env var
- **Passwords**: bcrypt hashed (Argon2 supported, auto-upgrade)
- **2FA passwords**: Used immediately, NEVER stored
- **Signal logs**: Contain only signal text and payloads (no credentials)

### 8.2 Data in Transit
- **All communication**: TLS 1.3 (HTTPS enforced)
- **API authentication**: JWT Bearer tokens in Authorization header
- **QStash**: Signed with `QSTASH_CURRENT_SIGNING_KEY` + `QSTASH_NEXT_SIGNING_KEY`
- **Workflow endpoints**: Validate Upstash-Signature header before processing

### 8.3 Rate Limiting
- Registration: 3 requests/minute
- Login: 5 requests/minute
- Forgot password: 3 requests/minute
- Telegram auth: Exponential backoff on failures

### 8.4 CORS
- Local mode: allows `http://localhost:5173` and `http://localhost:3000`
- Production: allows configured `FRONTEND_URL` only
- Credentials enabled, all methods and headers allowed

### 8.5 Critical Rules
- NEVER commit `.env` files or Telegram session strings
- NEVER store user trading account credentials (only webhook URLs)
- NEVER log session strings, phone numbers, or 2FA passwords
- NEVER modify SageMaster core platform code (standalone integration only)

---

## 9. Testing

### 9.1 Coverage Summary
- **254+ test cases** across 18 test modules
- **6,307 lines** of test code
- **Core coverage**: Parsing accuracy, webhook dispatch, multi-destination routing, authentication, database operations, encryption

### 9.2 Test Modules

| Module | Focus |
|--------|-------|
| test_openai_parser.py | AI signal parsing accuracy against fixtures |
| test_webhook.py | V1/V2 payload construction, dispatch |
| test_webhook_payloads.py | Payload format validation |
| test_mapper.py | Multi-destination routing, symbol replacement, risk overrides |
| test_telegram.py | Telethon client mocking, session encryption |
| test_routes.py | API endpoints, JWT auth, tier enforcement |
| test_models.py | Pydantic model validation |
| test_notifications.py | Email/Telegram notification dispatch |
| test_qstash_auth.py | QStash signature verification |
| test_workflow_e2e.py | End-to-end: signal → parse → map → dispatch → log |

### 9.3 Test Fixtures
- **10 diverse trading signals**: EURUSD long, GOLD sell, BTC/USDT sell, GBPJPY long, etc.
- **3 non-signals**: Market analysis, trade management, general chat
- **Expected payloads**: JSON expectations for each signal (validated against parser output)

### 9.4 Run Tests
```bash
pytest -v tests/                     # All tests
pytest -v tests/test_openai_parser.py # Parsing accuracy
pytest -v tests/test_workflow_e2e.py  # Full pipeline
```

---

## 10. Infrastructure

### 10.1 Production Stack

| Service | Provider | Purpose |
|---------|----------|---------|
| Backend + Listener | Railway | FastAPI server + persistent Telegram worker |
| Database | Neon | Serverless PostgreSQL (scales to zero) |
| Message Queue | Upstash QStash | HTTP-based message queue |
| Workflows | Upstash Workflow | Durable multi-step signal processing |
| Cache | Upstash Redis | Session caching, rate limiting |
| AI | OpenAI | GPT-4o-mini for signal parsing |
| Email | Resend | Notification emails |

### 10.2 Environment Variables

**Required**:
- `LOCAL_MODE` — true/false
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `OPENAI_API_KEY` — OpenAI API key
- `TELEGRAM_API_ID` — from my.telegram.org
- `TELEGRAM_API_HASH` — from my.telegram.org
- `JWT_SECRET_KEY` — for JWT signing (change in production!)
- `ENCRYPTION_KEY` — Fernet key for session encryption

**Production only**:
- `QSTASH_TOKEN`, `QSTASH_CURRENT_SIGNING_KEY`, `QSTASH_NEXT_SIGNING_KEY`
- `UPSTASH_REDIS_URL`, `UPSTASH_REDIS_TOKEN`
- `RESEND_API_KEY`

**Frontend**:
- `VITE_API_URL` — Backend API base URL (default: `http://localhost:8000`)

### 10.3 Local Development

```bash
docker-compose up --build    # Starts: api, listener, frontend, db, redis
```

Services: API (port 8000), Frontend (port 5173), PostgreSQL (port 5432), Redis (port 6379)

---

## 11. Frontend Architecture

### 11.1 Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Vite 8 + React 19 |
| Language | TypeScript 5.4 |
| Styling | Tailwind CSS 4 (emerald dark theme, Upstash-inspired) |
| Components | Hand-built on Radix UI primitives (not shadcn/ui dependency) |
| Server State | TanStack React Query v5 |
| Forms | React Hook Form + Zod |
| Icons | Lucide React |
| Toasts | Sonner |
| Theme | Custom `useTheme` hook (light/dark toggle, localStorage-persisted) |

### 11.2 Design System
- **Brand color**: Emerald green (dark: `oklch(0.72 0.19 163)`, light: `oklch(0.50 0.17 163)`)
- **Dark mode**: Rich zinc surfaces (bg → card → muted layering), minimal shadows
- **Status colors**: Emerald (success/active), Rose (failed/error), Amber (ignored/warning)
- **Typography**: Inter (UI) + JetBrains Mono (data/code)
- **Cards**: 16px border-radius, no shadows in dark mode (depth via surface contrast)

### 11.3 Component Library

**UI Primitives** (18 components): Button (6 variants, 7 sizes), Card, Input, Badge, Label, Form, Tooltip, DropdownMenu, Sheet, Select, Textarea, Switch, RadioGroup, Skeleton, Table, Separator, AlertDialog, Sonner

**Layout** (4): DashboardLayout, Sidebar (56px icon bar), Header, MobileNav (sheet overlay)

**Forms** (7): RoutingRuleWizard, StepSelectChannel, StepSetDestination, StepActions, StepSymbolMappings, TelegramConnectForm, TemplateBuilder

**Tables** (3): RoutingRulesTable, SignalLogsTable, LogDetailRow

**Shared** (5): StatusBadge, EmptyState, LoadingSpinner, TierGate, SignalDetailPanel

---

## 12. Implementation Status

### V1 MVP — COMPLETE
- [x] AI signal parsing (GPT-4o-mini)
- [x] Multi-destination routing (1 channel → N webhooks)
- [x] Per-destination symbol mapping
- [x] V1 & V2 webhook schemas (Forex & Crypto)
- [x] Telegram authentication (MTProto, 2FA, session encryption)
- [x] Full dashboard UI (React/TypeScript)
- [x] 4-step routing rule wizard with state preservation
- [x] Signal logs with filtering, pagination, live mode, detail panel
- [x] Tier enforcement (Free/Starter/Pro/Elite)
- [x] Email notifications
- [x] Telegram bot notifications (Starter+)
- [x] Settings (account, security, notifications, subscription)
- [x] Setup wizard (3-step onboarding)
- [x] Webhook testing
- [x] Template builder (visual + JSON modes)
- [x] Enabled actions configuration
- [x] Keyword blacklist
- [x] Custom AI instructions per route
- [x] Dark mode (emerald fintech theme)
- [x] Responsive design (mobile, tablet, desktop)
- [x] Test suite (254+ cases)
- [x] Docker Compose local dev
- [x] 13 Alembic migrations

### V2 — PLANNED
- [ ] Multiple TPs (TP1, TP2, TP3 array support)
- [ ] Provider commands (Close Half, Close All, Move SL to Entry)
- [ ] Trailing SL support
- [ ] MT5 EA source integration

### V3 — PLANNED
- [ ] Equity Guardian (global daily loss limits)
- [ ] News filter (30-min pause around news events)
- [ ] Analytics dashboard (win rate, drawdown, profitability)
- [ ] Backtesting engine
- [ ] Discord source integration

---

## 13. Key User Flows (End-to-End)

### 13.1 First-Time User
```
Register → Auto-redirect to Setup Wizard → Connect Telegram (phone → code → 2FA)
→ Create Route (channel → destination → actions) → Listen for First Signal
→ Celebration Screen → Dashboard
```

### 13.2 Daily Operations
```
Dashboard: Check status → View recent signals → Monitor success rate
Logs: Filter by status/route → Click signal for details → Review pipeline
Routes: Toggle active/paused → Edit settings → Test webhook
```

### 13.3 Signal Processing (Automatic)
```
Telegram message arrives → Listener detects in configured channel
→ QStash queues processing → Workflow starts
→ Step 1: GPT-4o-mini parses signal text
→ Step 2: For each active route: apply symbol mapping + risk overrides
→ Step 3: Construct V1/V2 payload per destination type
→ Step 4: HTTP POST to each webhook URL
→ Step 5: Log result (success/failed/ignored) per destination
→ Notification sent if configured (email/Telegram)
```

### 13.4 Error Recovery
```
Signal fails → Logged as "failed" with error message
→ Dashboard shows in "Recent Failures" card
→ Logs page: filter by "Failed" → click for detail panel
→ Detail panel shows: error message, raw message, parsed data
→ User can: fix route config, test webhook, retry manually
```
