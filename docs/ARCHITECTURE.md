# System Architecture & Directory Layout

## 1. Directory Structure

The project is organized into distinct modules to separate concerns and facilitate agentic development.

```
sgm-telegram-signal-copier/
├── src/
│   ├── main.py                 # FastAPI application entry point
│   ├── api/                    # Internal REST API endpoints
│   │   ├── routes.py           # Route definitions
│   │   └── workflow.py         # Upstash Workflow endpoints
│   ├── core/                   # Core Business Logic (No Infrastructure Dependencies)
│   │   ├── interfaces.py       # Protocols (SignalSource, Parser, Dispatcher)
│   │   ├── models.py           # Pydantic models (RawSignal, ParsedSignal)
│   │   ├── parser.py           # Abstract parser logic
│   │   ├── mapper.py           # Symbol mapping & multi-destination routing logic
│   │   └── security.py         # Encryption utilities
│   ├── adapters/               # Infrastructure Adapters
│   │   ├── telegram/           # Telethon MTProto client (implements SignalSource)
│   │   ├── openai/             # OpenAI API client (implements Parser)
│   │   ├── webhook/            # HTTP client for SageMaster (implements Dispatcher)
│   │   ├── db/                 # Neon PostgreSQL (SQLAlchemy)
│   │   ├── redis/              # Upstash Redis client
│   │   └── qstash/             # Upstash QStash publisher
├── tests/                      # Test suite
│   ├── fixtures/               # Test data (signals, payloads)
│   ├── test_telegram.py        # Telegram module tests
│   ├── test_parser.py          # AI parser tests
│   └── test_webhook.py         # Webhook dispatcher tests
└── docs/                       # Agentic documentation
```

## 2. Infrastructure Overview (Hybrid Serverless)

The system uses a hybrid serverless architecture, combining persistent workers with serverless event-driven pipelines. It supports two modes of operation via the `LOCAL_MODE` environment variable.

### 2.1 Production Mode (`LOCAL_MODE=false`)
-   **Hosting**: Railway (charges by-the-second for active compute)
-   **Database**: Neon (Serverless PostgreSQL, scales to zero)
-   **Message Queue / Workflows**: Upstash QStash & Upstash Workflow
-   **Caching / Rate Limiting**: Upstash Redis
-   **Backend Framework**: Python 3.11+ with FastAPI
-   **Telegram Client**: Telethon (MTProto API)
-   **AI Engine**: OpenAI API (GPT-4o-mini)

### 2.2 Local Development Mode (`LOCAL_MODE=true`)
To enable fully local development without requiring cloud accounts (except OpenAI/Telegram), the system uses Dependency Injection to swap adapters:
-   **Database**: Local PostgreSQL container
-   **Message Queue / Workflows**: Bypassed. The Listener calls the Parser directly in-process.
-   **Caching**: Local Redis container
-   **Signal Injection**: A mock `/api/dev/inject-signal` endpoint allows testing the pipeline without a real Telegram account.

## 3. Data Flow & Component Interactions

### 3.1 Telegram Authentication Flow
1.  User submits phone number via the frontend dashboard.
2.  `src/api/routes.py` receives the request and calls `src/telegram/auth.py`.
3.  `auth.py` initiates the login process with Telegram, which sends a code to the user.
4.  User submits the code via the frontend.
5.  `auth.py` completes the login and securely stores the encrypted session string in the **Neon PostgreSQL** database.

### 3.2 Signal Processing Pipeline (Event-Driven & Multi-Destination)
Because the Telegram MTProto API requires a persistent connection, the listener runs as a long-running Railway worker. However, the processing pipeline is decoupled using Upstash in production.

1.  **Interception**: `src/adapters/telegram/listener.py` (running as a persistent Railway worker) detects a new message.
2.  **Queueing**: The listener wraps it in a `RawSignal` model and passes it to the `QueuePort`.
    *   *Production*: Publishes to an **Upstash QStash** topic via HTTP POST.
    *   *Local Mode*: Calls the parser function directly in-process.
3.  **Workflow Trigger**: QStash triggers the **Upstash Workflow** endpoint (`/api/workflow/process-signal`) on the FastAPI backend.
4.  **Parsing (Step 1)**: The workflow calls the OpenAI adapter to extract trading parameters into a `ParsedSignal` model.
5.  **Routing & Mapping (Step 2)**: The workflow queries the database for all active **Routing Rules** (Destinations) associated with this Telegram channel. For each destination, it applies specific symbol mappings and risk overrides.
6.  **Dispatch (Step 3)**: The workflow constructs the JSON payload (V1 or V2) and sends an HTTP POST to *each* destination's SageMaster webhook URL.
7.  **Logging (Step 4)**: The results are logged to the database.

*Advantage*: Upstash Workflow automatically retries failed steps (e.g., if the SageMaster API is temporarily down) without blocking the Telegram Listener. In Local Mode, this complexity is bypassed for rapid testing.

## 4. Critical Security & Infrastructure Notes

*   **Telegram IP Blocking**: Telegram occasionally blocks shared PaaS IP ranges (including Railway). To mitigate this, the Telegram Listener must be configured to route its MTProto connection through a proxy (e.g., a Cloudflare Worker proxy or a dedicated IP) if connection timeouts occur.
*   **Session Storage**: Telethon session strings are encrypted and stored in the Neon PostgreSQL database, but actively cached in Upstash Redis for fast startup when the Railway worker restarts.
