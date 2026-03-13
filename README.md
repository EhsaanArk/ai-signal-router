# SageMaster Telegram Signal Copier

A cloud-based service that intercepts trading signals from Telegram channels and routes them to SageMaster accounts via webhook.

## Overview

This project acts as a bridge between Telegram signal providers and the SageMaster platform. It uses the Telegram MTProto API to read messages from channels the user is subscribed to, parses the unstructured text using an AI engine (OpenAI GPT-4o-mini), and constructs a structured JSON payload. 

A core feature is **Multi-Destination Routing**: a single Telegram signal can be routed to multiple SageMaster webhook URLs simultaneously, each with its own symbol mappings and risk settings. This payload is then dispatched to the user's unique SageMaster webhook URLs, allowing SageMaster to route the order to the user's connected broker.

**Important Note**: SageMaster performs *order routing*, not execution. This system simply triggers the routing process based on the user's predefined strategy.

## Documentation

This repository is structured for **Spec-Driven Development** using AI coding agents (like Claude Code).

- If you are an AI agent, start by reading `CLAUDE.md` or `AGENTS.md`.
- If you are a human developer, start with the high-level product brief in `docs/SPEC.md`.

### Key Specifications
- [System Architecture](docs/ARCHITECTURE.md)
- [Database Schema](docs/DATABASE_SCHEMA.md)
- [Webhook Payloads](docs/WEBHOOK_PAYLOADS.md)
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)
- [Testing Strategy](docs/TESTING_STRATEGY.md)

## Design Philosophy
The project follows **Clean Architecture (Ports & Adapters)**. The core parsing and mapping logic (`src/core/`) has no dependencies on infrastructure. All inputs (Telegram, MT5, Discord) implement a `SignalSource` interface, making the system highly extensible for future signal sources.

## Tech Stack (Hybrid Serverless)

- **Backend**: Python 3.11+, FastAPI (Hosted on Railway)
- **Containerization**: Docker & Docker Compose
- **Telegram Client**: Telethon (Persistent worker on Railway)
- **AI Parsing**: OpenAI API
- **Database**: Neon (Serverless PostgreSQL)
- **Message Queue / Workflows**: Upstash QStash & Upstash Workflow
- **Session Storage**: Upstash Redis
- **Frontend**: React 18, TypeScript

## Quick Start

1. Clone the repository.
2. Copy `.env.example` to `.env` and fill in your credentials (Telegram API ID/Hash, OpenAI API Key, Database URL).
3. Run via Docker Compose: `docker-compose up --build`
4. The API will be available at `http://localhost:8000`.

For full deployment instructions, see the [Deployment Guide](docs/DEPLOYMENT_GUIDE.md).
