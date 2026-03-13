# Deployment Guide

This document provides comprehensive instructions for deploying the SageMaster Telegram Signal Copier. The system uses a hybrid serverless architecture, relying on Railway for compute, Neon for the database, and Upstash for queuing and caching.

## 1. Prerequisites

Before deploying, ensure you have accounts created on the following platforms:
- **Railway** (Compute hosting)
- **Neon** (Serverless PostgreSQL)
- **Upstash** (Redis and QStash)
- **OpenAI** (API key for the parsing engine)
- **Telegram API** (API ID and Hash from my.telegram.org)

## 2. Environment Variables

The system requires the following environment variables to function correctly. These must be configured in your Railway project.

| Variable | Description | Source |
|----------|-------------|--------|
| `DATABASE_URL` | Connection string for the PostgreSQL database | Neon |
| `UPSTASH_REDIS_REST_URL` | REST URL for the Redis cache | Upstash |
| `UPSTASH_REDIS_REST_TOKEN` | REST Token for the Redis cache | Upstash |
| `QSTASH_TOKEN` | Token for publishing to QStash | Upstash |
| `QSTASH_CURRENT_SIGNING_KEY` | Key for verifying QStash callbacks | Upstash |
| `QSTASH_NEXT_SIGNING_KEY` | Secondary key for verifying QStash callbacks | Upstash |
| `OPENAI_API_KEY` | API key for the GPT-4o-mini parser | OpenAI |
| `TELEGRAM_API_ID` | Your Telegram application API ID | Telegram |
| `TELEGRAM_API_HASH` | Your Telegram application API Hash | Telegram |
| `ENCRYPTION_KEY` | 32-byte base64 encoded key for encrypting sessions | Generate locally |
| `API_BEARER_TOKEN` | Secret token for authenticating internal API requests | Generate locally |

## 3. Local Development (Docker Compose)

For local development and testing, a `docker-compose.yml` file is provided. This spins up the FastAPI backend, the Telegram Listener worker, a local PostgreSQL database, and a local Redis instance.

By setting `LOCAL_MODE=true` in your `.env` file, the system automatically bypasses Upstash QStash and Upstash Workflow, executing the pipeline sequentially in-process. This allows you to test the entire application locally without needing cloud accounts (except for OpenAI and Telegram).

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Fill in your `OPENAI_API_KEY`, `TELEGRAM_API_ID`, and `TELEGRAM_API_HASH`. The local database and Redis connection strings are already pre-filled.
3. Start the services:
   ```bash
   docker-compose up --build
   ```
4. The API will be available at `http://localhost:8000`.

### 3.1 Testing with the Mock Signal Injector
In `LOCAL_MODE`, a special endpoint is enabled to let you test the pipeline without needing a real Telegram account or channel:
- **POST** `http://localhost:8000/api/dev/inject-signal`
- **Body**: `{"text": "BUY GOLD @ 2000 SL 1990 TP 2020", "channel_id": "-100123456789"}`
This will run the signal through the parser, mapper, and dispatcher just as if it came from Telegram.

## 4. Production Deployment (Railway)

Railway is used for production hosting. The project requires two separate services within a single Railway Project: the API Service and the Listener Worker.

### 4.1 Initial Setup

1. Create a new Project in Railway.
2. Connect your GitHub repository to the project.
3. Railway will automatically detect the `Dockerfile` and attempt to build the project.

### 4.2 Configure the API Service

This service handles the FastAPI backend, dashboard requests, and Upstash Workflow callbacks.

1. In the Railway dashboard, select the newly created service and rename it to `sgm-api`.
2. Go to the **Variables** tab and input all the environment variables listed in Section 2. **Ensure `LOCAL_MODE` is set to `false` or removed.**
3. Go to the **Settings** tab.
4. Under **Deploy**, set the **Start Command** to:
   ```bash
   uvicorn src.main:app --host 0.0.0.0 --port $PORT
   ```
5. Under **Networking**, click **Generate Domain** to expose the API publicly. Note this URL for the Upstash QStash configuration.

### 4.3 Configure the Listener Worker

This service runs the persistent Telethon MTProto client to listen for new Telegram messages.

1. In the Railway Project canvas, click **Create** -> **GitHub Repo** and select the same repository again.
2. Rename this second service to `sgm-listener`.
3. Go to the **Variables** tab. Instead of copying all variables manually, use Railway's Reference Variables to link them from the API service (e.g., `${{sgm-api.DATABASE_URL}}`).
4. Go to the **Settings** tab.
5. Under **Deploy**, set the **Start Command** to:
   ```bash
   python -m src.adapters.telegram.listener
   ```
6. Ensure **Networking** is NOT configured with a public domain. This worker does not need to accept incoming HTTP requests.

### 4.4 Upstash QStash Configuration

Once the API service is deployed and has a public domain, configure Upstash QStash to route messages to it.

1. In the Upstash Console, navigate to QStash.
2. The Telegram Listener will publish messages to a topic (e.g., `sgm-signals`).
3. Create an endpoint for this topic pointing to your Railway API domain:
   `https://<your-railway-domain>/api/workflow/process-signal`

## 5. Database Migrations

Database schema management is handled via SQLAlchemy and Alembic (or raw SQL scripts as defined in `DATABASE_SCHEMA.md`).

To apply the initial schema to your Neon database:
1. Connect to the Neon database using a local PostgreSQL client (e.g., `psql` or pgAdmin).
2. Execute the SQL statements provided in `docs/DATABASE_SCHEMA.md`.

## 6. Post-Deployment Verification

After deployment, verify the system is functioning correctly:

1. Check the Railway logs for both `sgm-api` and `sgm-listener`. Ensure there are no startup errors.
2. Verify the `sgm-listener` logs indicate a successful connection to the Telegram API.
3. Use the API (or the frontend dashboard once built) to authenticate a test Telegram account.
4. Post a test signal in a monitored channel and verify it appears in the `signal_logs` table in the Neon database.
