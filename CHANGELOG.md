# Changelog

All notable changes to this project will be documented in this file.

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
