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
