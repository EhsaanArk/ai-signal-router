# Changelog

All notable changes to this project will be documented in this file.

## [0.1.4.2] - 2026-03-28

### Fixed
- Race condition in `_handle_auth_key_duplicated`: heartbeat path called `_restart_listener_for_user_inner` without the per-user lock, allowing concurrent operations to create duplicate Telegram listeners
- Latent deadlock in escalation path: `_stop_listener_for_user` (lock-acquiring) was called from startup context where the lock was already held

## [0.1.4.1] - 2026-03-27

### Changed
- CI pre-merge checks now use `dorny/paths-filter` to skip backend tests when only frontend files change and vice versa
- Backend filter covers: `src/`, `tests/`, `requirements*.txt`, `pyproject.toml`, `alembic/`, `Dockerfile`, `docker-compose*.yml`, `.github/workflows/ci.yml`
- Frontend filter covers: `frontend/**`

### Fixed
- Removed `deployment_status` trigger from staging post-deploy workflow (was firing on ALL branch deploys including production)
- Added missing `outputs` declaration on QA Guardian job so the downstream PR comment job can read score, verdict, and summary

## [0.1.4.0] - 2026-03-27

### Fixed
- Telegram bot commands (/start, /status, /unlink) crash with 500 for users with chat_id > 2^31 (int32 overflow on JSONB CAST)
- Changed `.as_integer()` to `.as_bigint()` for both `telegram_bot_chat_id` and `telegram_user_id` JSONB queries

## [0.1.3.0] - 2026-03-26

### Added
- Vibe Trading Bot: send trading signals via Telegram DM to @SageRadarBot instead of the SageMaster UI
- Typed Pydantic sub-models for Telegram Bot API updates (TelegramUser, TelegramChat, TelegramMessage, TelegramCallbackQuery)
- Bot API helpers on TelegramNotifier: send_message, answer_callback_query, edit_message_text with shared _post method
- Confirmation flow with Redis-backed state (5-min TTL, atomic GETDEL for idempotency)
- Auto-create routing rule on /start account linking (clones user's first active rule)
- `source_type` field on RawSignal/RawSignalMeta — parameterized across pipeline (replaces hardcoded "telegram")
- `BOT_ENABLED` feature flag (default false) — gates signal processing, commands always work
- JSONB functional indexes on `telegram_bot_chat_id` and `telegram_user_id` for fast user lookup
- `getdel()` method on CachePort protocol and both Redis/InMemory adapters
- 23 unit tests for bot schemas, models, helpers, cache, and linking

### Changed
- Bot DM routing rules (`bot_dm_*`) filtered from dashboard API to prevent UI leakage
- Dispatch wrapped in `asyncio.wait_for(15s)` to prevent 45s worst-case blocking in Telegram callback
- All bot messages use Markdown v1 (simpler escaping than MarkdownV2)
- Lazy imports in telegram.py moved to top-level for clarity

### Fixed
- Group mode deferred to Phase 2 (Telegram privacy mode and anonymous admins make it fragile)

## [0.1.2.0] - 2026-03-26

### Added
- Webhook contract tests (26 tests): deterministic validation of all SageMaster payload formats (Forex V1/V2, Crypto, management actions, edge cases)
- Parser fixture regression tests (82 tests): validate all 25 signal fixtures against expected payloads without OpenAI calls
- Pipeline smoke tests in production CI: real Telegram-to-SageMaster E2E verification post-deploy
- Sentry error check in both staging and production CI: queries new issues within 10 minutes of deploy
- QA Guardian confidence scoring in production CI: SHIP/INVESTIGATE/BLOCK verdicts with 0-100 score

### Changed
- Production post-deploy workflow upgraded from 3-stage (health + API tests + summary) to 6-stage (+ pipeline smoke + Sentry + QA Guardian)
- Staging QA Guardian prompt aligned with production (env vars instead of sed substitution)
- All CI test steps now report `skipped` instead of false-green `pass` when 0 tests run (fixes 0/0 = pass bug)
- Staging QA Guardian now includes pipeline and Sentry results in scoring

### Fixed
- False-green CI results when secrets are missing (0 passed / 0 failed no longer reports as pass)
- Duplicate test files removed (`test_api_regression 2.py`, `test_pipeline_smoke 2.py`)

## [0.1.1.0] - 2026-03-23

### Added
- Signal Marketplace V1: admin-curated provider directory with verified performance stats
- Public marketplace page (`/marketplace`) — browsable without authentication
- Data-forward provider cards with win rate, P&L, drawdown, and track record
- One-click subscribe flow with legal consent (disclaimer + checkbox)
- Marketplace-first onboarding path — new users can subscribe without connecting Telegram
- Sorting (win rate, P&L, signals, subscribers) and filtering (forex/crypto/both) on provider directory
- User subscriptions management page (`/dashboard/subscriptions`)
- Admin marketplace dashboard with provider CRUD and marketplace-wide stats (`/admin/marketplace`)
- Marketplace sidebar nav integration (between Signal Routes and Signal Logs)
- Core marketplace logic: fan-out, stats computation, subscribe/unsubscribe lifecycle
- 10 new API endpoints (public, authenticated, admin) with rate limiting
- DB migration: 3 new tables (marketplace_providers, marketplace_subscriptions, marketplace_consent_log) + source_type column on signal_logs
- `MARKETPLACE_ENABLED` feature flag gates all marketplace fan-out behavior
- 20 marketplace-specific unit tests covering fan-out, stats, subscribe/unsubscribe
- Sample provider seed script (`scripts/seed_marketplace.py`)
- Design doc (`docs/designs/SIGNAL-MARKETPLACE.md`) with full UX specifications

### Security
- Rate limiting on public marketplace endpoints (60/min) and subscribe/unsubscribe (10/min)
- Re-subscription bug fix (unique constraint + soft-delete conflict)
- Consent version tracking via parameterized `DISCLAIMER_VERSION` constant
- Zero changes to protected signal pipeline files (workflow, parser, mapper, dispatcher)
