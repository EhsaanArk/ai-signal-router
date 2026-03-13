# SageMaster Telegram Signal Copier - Agent Instructions

This file provides context for AI coding assistants (Claude Code, Cursor, Aider, etc.) working on this repository.

## Project Overview
A cloud-based Telegram Signal Copier that intercepts trading signals from Telegram channels via the MTProto API, parses them using an LLM, and routes them to SageMaster accounts via webhook.

## Tech Stack (Hybrid Serverless)
- Python 3.11+, FastAPI, Telethon, OpenAI API
- Neon (Serverless PostgreSQL), Upstash Redis
- Upstash QStash & Upstash Workflow (event-driven pipeline)
- Railway (hosting), React 18, TypeScript

## Commands
- **Install**: `pip install -r requirements.txt`
- **Install Upstash SDK**: `pip install upstash-workflow upstash-redis upstash-qstash`
- **Run Dev**: `uvicorn src.main:app --reload`
- **Run Local QStash**: `npx @upstash/qstash-cli dev`
- **Test**: `pytest -v tests/`

## Core Rules
1. **No Execution**: SageMaster performs "order routing", not execution. Never describe the system as executing trades.
2. **Security**: NEVER commit Telegram session strings or `.env` files. Always encrypt session strings at rest.
3. **Platform Integrity**: Do not modify the SageMaster core platform code.

## Documentation Map
For detailed specifications, read the following files:
- `docs/SPEC.md`: High-level product brief and boundaries.
- `docs/ARCHITECTURE.md`: System design and directory layout.
- `docs/WEBHOOK_PAYLOADS.md`: Exact JSON schemas for SageMaster integration.
- `docs/DATABASE_SCHEMA.md`: SQL table definitions.
- `docs/TESTING_STRATEGY.md`: Verification criteria and test fixtures.

## Specialized Skills
If you are working on specific modules, load these skills:
- Working on `src/parser/`? Read `.claude/skills/signal-parsing/SKILL.md`
- Working on `src/webhook/`? Read `.claude/skills/sagemaster-integration/SKILL.md`
