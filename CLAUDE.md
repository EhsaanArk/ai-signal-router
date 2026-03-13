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

## Git Workflow
- Branch naming: `feature/SGM-XXX-description` or `bugfix/SGM-XXX-description`
- Commit format: `type(scope): description` (e.g., `feat(parser): add support for image signals`)
- Always run tests and linter before committing.

## Project Boundaries & Constraints
- **NEVER** commit Telegram session strings or `.env` files to version control.
- **NEVER** modify the SageMaster core platform code; this is a standalone integration.
- **NEVER** store user trading account credentials; we only store the SageMaster webhook URL.
- **Multi-Destination Routing**: The system must support routing 1 Telegram channel to N SageMaster webhooks (Destinations), each with its own risk settings and symbol mappings.
- **CRITICAL TERMINOLOGY**: Always use the term "order routing" or "route" instead of "execution" when referring to SageMaster's function. SageMaster does not perform the final execution.

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
