# SageMaster Telegram Signal Copier

## Project Overview
This project is a cloud-based Telegram Signal Copier that intercepts trading signals from Telegram channels via the MTProto API, parses them using an LLM, and routes them to SageMaster accounts via webhook.

## Infrastructure (Hybrid Serverless)
- **Hosting**: Railway (persistent Telegram Listener worker + FastAPI backend)
- **Database**: Neon (Serverless PostgreSQL)
- **Message Queue / Workflows**: Upstash QStash & Upstash Workflow
- **Session Cache**: Upstash Redis
- **AI**: OpenAI API (GPT-4o-mini)

## Build & Test Commands
- Install dependencies: `pip install -r requirements.txt`
- Install Upstash SDK: `pip install upstash-workflow upstash-redis upstash-qstash`
- Run development server: `uvicorn src.main:app --reload`
- Run local QStash server: `npx @upstash/qstash-cli dev`
- Run via Docker Compose: `docker-compose up --build`
- Run tests: `pytest -v tests/`
- Run linter: `flake8 src/`
- Type checking: `mypy src/`

## Local UI Testing (for all agents)

When you need to visually test the UI (for `/qa`, `/design-review`, or manual verification), follow this standard flow:

### 1. Start the app
```bash
docker compose up -d --build
docker compose exec api alembic upgrade head
```
Services: Frontend (`localhost:5173`), API (`localhost:8000`), DB (`localhost:5432`), Redis (`localhost:6379`)

### 2. Create a test admin user
```bash
# Register via API
curl -s http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"Test1234!"}'

# Promote to admin in DB
docker compose exec db psql -U postgres -d sgm_copier \
  -c "UPDATE users SET is_admin = true, email_verified = true WHERE email = 'admin@test.com';"
```

### 3. Login via gstack browse
```bash
B="$(git rev-parse --show-toplevel)/.claude/skills/gstack/browse/dist/browse"
$B goto "http://localhost:5173"
$B snapshot -i                    # find form element IDs
$B fill @eN "admin@test.com"     # email field (use actual @e ID from snapshot)
$B fill @eN "Test1234!"          # password field
$B click @eN                     # Sign In button
$B goto "http://localhost:5173/admin/parser"  # or any target page
```

### 4. Interact & screenshot
```bash
$B snapshot -i                   # list elements with @e IDs
$B click @eN                     # click by element ID
$B fill @eN "text"              # type into input
$B snapshot -a -o "path.png"    # annotated screenshot
$B responsive "prefix"           # mobile + tablet + desktop screenshots
$B viewport 375x812             # switch to mobile
```

### 5. Cleanup
```bash
docker compose down              # stop containers
docker compose down -v           # stop + delete volumes (fresh DB next time)
```

**Important:** Element `@e` IDs change after navigation. Always run `$B snapshot -i` to get fresh IDs before interacting. The `.env` file must have `OPENAI_API_KEY` for parser test sandbox to work.

## Design Philosophy & Code Style
- **Clean Architecture (Ports & Adapters)**: `src/core/` MUST NOT import from `src/adapters/`. Core logic only defines interfaces (Protocols) that adapters implement.
- **Local Mode Fallbacks**: All adapters MUST have a local fallback when `LOCAL_MODE=true` (e.g., bypass QStash, use local Redis/Postgres).
- **SignalSource Abstraction**: All signal inputs (Telegram, MT5, Discord) must implement the `SignalSource` interface.
- Use Python 3.11+ features (type hints, async/await).
- Follow PEP 8 formatting guidelines.
- Use `pydantic` for all data validation and JSON serialization.
- All Telegram interaction must use the `Telethon` library asynchronously.

## Git Workflow & Deployment

### Branches
- `main` — production-ready code. Railway production environment auto-deploys from this branch.
- `staging` — integration/testing branch. Railway staging environment auto-deploys from this branch.
- Feature/bugfix branches are created off `staging`.

### Branch Naming
- `feature/SGM-XXX-description` or `bugfix/SGM-XXX-description`

### Commit Format
- `type(scope): description` (e.g., `feat(parser): add support for image signals`)

### Development Flow
1. Create a feature/bugfix branch off `staging`
2. Develop and commit locally
3. Push branch → create PR targeting `staging`
4. Merge to `staging` → Railway staging auto-deploys
5. Test on staging environment
6. When staging is validated, create PR from `staging` → `main`
7. Merge to `main` → Railway production auto-deploys

### Hotfix Flow
For urgent production fixes:
1. Branch off `staging` (or `main` if critical)
2. Fix, push, merge to `staging` first
3. Test on staging, then PR `staging` → `main`

### Rules
- **Never push directly to `main`** — always go through `staging` first
- **Never force-push** to `main` or `staging`
- Always run tests and linter before committing
- PRs from `staging` → `main` should summarise all included changes
- **NEVER merge PRs to `main` without explicit user approval** — GitHub branch protection enforces this (1 review required). Agents may CREATE staging→main PRs but must STOP and ask the user to review and approve. This is a hard rule — violating it risks deploying untested code to production where real money is at stake.
- **After a staging→main merge**: merge `main` back into `staging` to keep histories in sync (`git checkout staging && git merge origin/main && git push`). Squash merges create new commit SHAs that cause divergence if this step is skipped.

### Multi-Agent Collaboration
When multiple Claude Code agents are working on this repo simultaneously:
1. **Each agent MUST work on its own feature/bugfix branch** — never commit directly to `staging` or `main`
2. **Branch off `staging`** at the start of the task: `git checkout -b feature/SGM-XXX-description staging`
3. **Pull latest staging** before branching: `git fetch origin && git checkout staging && git pull`
4. **Create a PR to `staging`** when work is complete — do not merge without user approval
5. **NEVER create or merge PRs targeting `main`** — only the user initiates production releases. If asked to "push to production", create the staging→main PR and STOP. Do not merge it.
6. **Never force-push** or rebase shared branches
7. **If you see uncommitted changes** in the working tree that aren't yours, stash them or ask the user — do not discard them

### Railway Environments
- **Staging**: `staging` branch — 3 services (API, Listener, Frontend)
  - API: `ai-signal-router-staging.up.railway.app`
  - Frontend: `profound-communication-staging.up.railway.app`
- **Production**: `main` branch — same 3-service architecture
- Both environments auto-deploy on push to their respective branches

## Project Boundaries & Constraints
- **NEVER** commit Telegram session strings or `.env` files to version control.
- **NEVER** modify the SageMaster core platform code; this is a standalone integration.
- **NEVER** store user trading account credentials; we only store the SageMaster webhook URL.
- **Multi-Destination Routing**: The system must support routing 1 Telegram channel to N SageMaster webhooks (Destinations), each with its own risk settings and symbol mappings.
- **CRITICAL TERMINOLOGY**: Always use the term "order routing" or "route" instead of "execution" when referring to SageMaster's function. SageMaster does not perform the final execution.

## Critical Signal Pipeline — Handle With Care

The following files form the live trading signal pipeline. Changes to these files directly affect real money. **Extra caution required.**

### Pipeline Flow
```
Telegram → Listener → QStash → API Workflow → OpenAI Parser → Mapper → Webhook Dispatcher → DB Log
```

### Protected Files
| File | Role |
|------|------|
| `src/adapters/telegram/listener.py` | Intercepts Telegram messages, builds RawSignal, enqueues to QStash |
| `src/adapters/qstash/publisher.py` | Publishes signals to QStash for async processing |
| `src/api/qstash_auth.py` | Verifies QStash JWT signatures on callbacks |
| `src/api/workflow.py` | Orchestrates the full signal processing pipeline |
| `src/adapters/openai/parser.py` | LLM-based signal parsing (system prompt + GPT-4o-mini) |
| `src/core/mapper.py` | Symbol mapping, action mapping, webhook payload construction |
| `src/adapters/webhook/dispatcher.py` | HTTP dispatch to SageMaster with retry logic |
| `src/core/models.py` | RawSignal, ParsedSignal, RoutingRule, DispatchResult |
| `src/core/interfaces.py` | Protocol definitions (SignalParser, QueuePort, etc.) |
| `src/adapters/db/models.py` | SignalLogModel, RoutingRuleModel, TelegramSessionModel |

### Rules for Pipeline Files
1. **Read before modifying** — always read the full file before making any changes
2. **Never remove existing logic** — only add or modify; if removing, explain why and confirm with user
3. **Preserve function signatures** — changing a signature breaks callers across the pipeline
4. **Never modify the OpenAI system prompt** (`parser.py`) without explicit user request
5. **Never change webhook payload structure** (`mapper.py` `build_webhook_payload()`) without explicit user request — SageMaster expects a specific JSON format
6. **Run tests after any pipeline change** — `pytest -v tests/`
7. **If unsure, ask** — never guess at pipeline behaviour; ask the user or read the code
8. **Update QA tests when modifying pipeline** — see "QA Orchestrator Maintenance" below

## QA Orchestrator — Automatic Test Maintenance

The QA Orchestrator validates the signal pipeline end-to-end. **Every agent must update QA tests when their changes affect the pipeline.** Follow the existing patterns in `tests/test_webhook_contract.py` and `tests/conftest.py`.

### When to update (triggers)

| You changed... | Update this... | How |
|----------------|---------------|-----|
| `src/core/models.py` (new action in `SignalAction`) | `tests/test_webhook_contract.py` | Add contract test — copy an existing test, use `_forex_rule()` / `_crypto_rule()` helpers in that file |
| `src/core/models.py` (new field on `ParsedSignal`) | `tests/fixtures/expected_payloads.json` | Add field to relevant fixture entries |
| `src/core/mapper.py` (new action mapping) | `tests/test_webhook_contract.py` | Add test for both forex AND crypto if applicable |
| `src/core/mapper.py` (payload structure change) | `tests/test_webhook_contract.py` | Update existing contract tests to match new structure |
| `src/adapters/openai/parser.py` (system prompt change) | `tests/fixtures/raw_signals.txt` + `expected_payloads.json` | Add new signal examples that exercise the prompt change |
| New signal type or format | Both fixture files + `tests/test_parser_fixtures.py` | Add to `_ENTRY_IDS`, `_MANAGEMENT_IDS`, or `_IGNORED_IDS` |
| `.github/workflows/post-deploy-*.yml` (new CI step) | Same workflow file | Include `if [ "$TOTAL" = "0" ]; then result=skipped` logic |
| New API endpoint | `tests/e2e/test_api_regression.py` | Add E2E test hitting the new endpoint |

### How to add tests

**Adding a webhook contract test** (most common — copy pattern from `test_webhook_contract.py`):
```python
# Use the private helpers already in test_webhook_contract.py: _forex_rule(), _crypto_rule()
def test_my_new_action():
    signal = ParsedSignal(action="my_action", symbol="XAUUSD")
    payload = build_webhook_payload(signal, _forex_rule("V1"))
    assert payload["type"] == "expected_action_type"
    assert payload["assistId"] == _ASSIST_ID
```

**Adding a parser fixture** (3 steps):
1. Append to `tests/fixtures/raw_signals.txt`: `--- SIGNAL N ---\n<raw message text>`
2. Append to `tests/fixtures/expected_payloads.json`: `{"id": "SIGNAL N", "parsed": {...}}`
3. Add `"SIGNAL N"` to the correct set in `tests/test_parser_fixtures.py`: `_ENTRY_IDS`, `_MANAGEMENT_IDS`, or `_IGNORED_IDS`

### QA test files reference

| File | Purpose | When to update |
|------|---------|---------------|
| `tests/conftest.py` | Shared fixtures — `sample_parsed_signal`, `sample_routing_rule_v1/v2`, sample constants | When adding new fixture patterns used across multiple test files |
| `tests/test_webhook_contract.py` | Validates `build_webhook_payload()` output matches SageMaster schemas | When mapper or models change |
| `tests/test_parser_fixtures.py` | Validates fixture signals are correctly classified | When parser prompt or signal types change |
| `tests/fixtures/raw_signals.txt` | 25+ raw signal examples (entry, management, non-signal) | When adding new signal formats |
| `tests/fixtures/expected_payloads.json` | Expected parse output for each fixture signal | Must stay in sync with raw_signals.txt |
| `tests/e2e/test_api_smoke.py` | API endpoint health + auth tests | When adding new endpoints |
| `tests/e2e/test_api_regression.py` | Full CRUD lifecycle + parse preview + marketplace tests | When adding new API features |
| `tests/e2e/test_pipeline_smoke.py` | Real Telegram → SageMaster E2E flow | When pipeline routing logic changes |
| `.github/workflows/post-deploy-staging.yml` | 7-stage staging CI pipeline | When adding new post-deploy checks |
| `.github/workflows/post-deploy-production.yml` | 6-stage production CI pipeline | When adding new post-deploy checks |

## Documentation Pointers
- High-level product brief: `@docs/SPEC.md`
- Phased feature roadmap and tiers: `@docs/PRODUCT_ROADMAP.md`
- System architecture and directory layout: `@docs/ARCHITECTURE.md`
- Database schema: `@docs/DATABASE_SCHEMA.md`
- SageMaster webhook JSON formats: `@docs/WEBHOOK_PAYLOADS.md`
- Internal API endpoints: `@docs/API_ENDPOINTS.md`
- Deployment guide (Docker/Railway): `@docs/DEPLOYMENT_GUIDE.md`
- Testing strategy and fixtures: `@docs/TESTING_STRATEGY.md`
- Security requirements: `@docs/SECURITY_REQUIREMENTS.md`
- Granular user stories: `@docs/USER_STORIES.md`
- Architecture diagrams: `@docs/diagrams/`
- GTM strategy: `@docs/launch/GTM_STRATEGY.md`
- DevOps runbook: `@docs/launch/DEVOPS_RUNBOOK.md`
- Support playbook: `@docs/launch/SUPPORT_PLAYBOOK.md`
- User guide: `@docs/launch/USER_GUIDE.md`

## Tooling & Workflow

This project uses **gstack skills** for development workflows and **specialist agents** for post-deploy monitoring. Together they cover the full lifecycle.

### Development Lifecycle

| Phase | Tool | Trigger |
|-------|------|---------|
| **Plan** | `/plan-eng-review` | Before starting implementation of a non-trivial feature |
| **Plan (strategic)** | `/plan-ceo-review` | When scoping a new product initiative or major pivot |
| **Build & Browse** | `/browse` | For all web browsing and manual QA — **NEVER use `mcp__claude-in-chrome__*` tools directly** |
| **Test** | `/qa` | Test web app flows, find + fix bugs iteratively |
| **Review** | `/review` | Before merging any PR — check for structural issues |
| **Ship** | `/ship` | Automated merge + test + version bump + PR creation |
| **Document** | `/document-release` | After shipping — sync docs with shipped code |
| **Monitor** | `sentry-monitor` agent | After deploy — check for new errors |
| **Verify** | `railway-ops` agent | After deploy — confirm services healthy |
| **Investigate** | `db-expert` agent | When debugging data issues |

### Specialist Agents (`.claude/agents/`)

Use these **proactively** — don't wait for the user to ask.

| Agent | When to invoke |
|-------|----------------|
| `sentry-monitor` | After deployments, when errors mentioned, post-deploy verification |
| `railway-ops` | Deployment status, service health, "is it deployed", "check staging" |
| `db-expert` | Data integrity, "check the DB", SQL queries, duplicate records |

### Auto-invoke triggers
- **After merging a PR to staging/main** → `railway-ops` to verify deploy, then `sentry-monitor` for errors
- **After `/ship` completes** → `railway-ops` to verify deploy, then `sentry-monitor` for errors
- **When debugging a Sentry error** → `sentry-monitor` first, then `db-expert` if data-related
- **When user asks "what's happening"** → `railway-ops` for service health

### gstack Skills Reference

All gstack skills live in `.claude/skills/gstack/`. If skills aren't working, run:
```
cd .claude/skills/gstack && ./setup
```

Available skills:
- `/browse` — Persistent headless browser for QA and web interaction
- `/plan-ceo-review` — CEO/founder-mode plan review
- `/plan-eng-review` — Engineering plan review (architecture, data flow, edge cases)
- `/review` — Pre-landing PR diff review
- `/ship` — Automated ship workflow (merge, test, version, PR)
- `/qa` — QA test + iterative bug fixing
- `/setup-browser-cookies` — Import cookies for authenticated browse sessions
- `/retro` — Weekly engineering retrospective
- `/document-release` — Post-ship documentation sync
