# Product Specification: SageMaster Telegram Signal Copier

## 1. Objective
Build a cloud-based Telegram Signal Copier that intercepts trading signals from Telegram channels and routes them to SageMaster accounts via webhook. This product acts as a bridge, parsing unstructured data from Telegram using an LLM and converting it into structured JSON payloads that SageMaster understands.

## 2. Tech Stack (Hybrid Serverless)
- **Backend**: Python 3.11+, FastAPI
- **Telegram Client**: Telethon (MTProto API)
- **AI Parsing**: OpenAI GPT-4o-mini via API
- **Database**: Neon (Serverless PostgreSQL)
- **Message Queue / Workflows**: Upstash QStash & Upstash Workflow
- **Session Storage**: Upstash Redis
- **Frontend**: React 18, TypeScript 5.4
- **Infrastructure**: Railway (for persistent Telegram listener & FastAPI backend)

*Note: A `LOCAL_MODE` environment variable allows running the entire stack locally via Docker Compose, bypassing Upstash and Neon in favor of local PostgreSQL, local Redis, and in-process function calls.*

## 3. Core Features (V1 MVP)
1. **Telegram MTProto Auth**: Authenticate users via phone number and login code to read channels they are subscribed to (userbot approach).
2. **AI Parsing Engine**: Extract trading parameters (Symbol, Direction, Entry, SL, TP) from diverse signal formats (text, images, conversational) using an LLM.
3. **Multi-Destination Routing**: Route a single parsed signal to multiple SageMaster webhook URLs simultaneously, each with its own symbol mappings and risk settings.
4. **Webhook Dispatcher**: Construct JSON payloads (V1 or V2) and dispatch HTTP POST requests to the user's unique SageMaster webhook URLs.
5. **Tier Enforcement**: Enforce subscription limits (Starter: 2 destinations, Pro: 5 destinations, Elite: 15 destinations).
6. **Standalone Dashboard**: A secure, separately branded web interface for users to manage connections, configure routing rules, and view logs.

## 4. Design Philosophy
- **Clean Architecture (Ports & Adapters)**: The core parsing and mapping logic (`src/core/`) MUST NOT depend on infrastructure. 
- **SignalSource Interface**: All signal inputs (Telegram, MT5 EA, Discord) must implement the `SignalSource` interface. This ensures the system is highly extensible for future phases.

## 5. Boundaries & Constraints
- **No Execution**: SageMaster performs **order routing**, not execution. The system must never be described as executing trades.
- **No Direct Broker Integration**: The system must only communicate with SageMaster webhooks, never directly with MT4/MT5 or other broker APIs.
- **Security**: Telegram session strings must be heavily encrypted at rest. Never commit session strings or `.env` files to version control.
- **Platform Integrity**: Do not modify the SageMaster core platform code (sfx.sagemaster.io or app.sagemaster.io). This is a standalone integration.
- **Data Privacy**: Do not store user trading account credentials. Only store the SageMaster webhook URL and necessary configuration data.

## 6. Success Criteria
- **Parsing Accuracy**: The AI Parsing Engine must achieve >95% accuracy on the test fixture set (`tests/fixtures/raw_signals.txt`).
- **Latency**: The end-to-end process (from signal detection to webhook dispatch) must complete in under 2 seconds on average.
- **Reliability**: The Webhook Dispatcher must handle 100 concurrent webhook deliveries without failure or data loss.
- **User Experience**: The onboarding flow must be clear and logical, prioritizing clarity over step count, to cater to both professional traders and beginners.
