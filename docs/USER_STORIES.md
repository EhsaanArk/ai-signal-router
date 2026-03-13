# User Stories & Acceptance Criteria

## Epic 1: Telegram Authentication

### US 1.1: Connect Telegram Account
**As a** user,
**I want to** connect my Telegram account using my phone number,
**So that** the system can read messages from the channels I am subscribed to.

**Acceptance Criteria:**
1. The UI provides an input field for the user's phone number (with country code).
2. The system initiates the MTProto login flow and requests a verification code from Telegram.
3. The UI prompts the user to enter the verification code sent to their Telegram app.
4. If the user has 2FA enabled, the UI prompts for their password.
5. Upon successful login, the system securely encrypts and stores the session string in the database.
6. The UI displays a success message and transitions to the channel selection step.

## Epic 2: Routing Rules (Multi-Destination)

### US 2.1: Create Routing Rule
**As a** user,
**I want to** create a routing rule that maps a specific Telegram channel to a SageMaster webhook URL,
**So that** signals from that channel are routed to my strategy.

**Acceptance Criteria:**
1. The UI allows the user to select a "Source" (a Telegram channel they are subscribed to).
2. The UI allows the user to enter a "Destination" (a SageMaster webhook URL).
3. The system validates that the URL matches the expected format (`https://api.sagemaster.io/deals_idea/...`).
4. The user can select the payload version (V1 or V2) for this specific destination.
5. The system saves this as a new record in the `routing_rules` table.

### US 2.2: Multi-Destination Routing
**As a** user,
**I want to** create multiple routing rules for the same Telegram channel,
**So that** a single signal can be sent to multiple SageMaster bots simultaneously.

**Acceptance Criteria:**
1. The UI allows the user to create another routing rule using a previously selected Telegram channel as the Source.
2. The user can provide a different SageMaster webhook URL as the Destination.
3. The system enforces the user's tier limit (e.g., Starter tier can only have 2 active routing rules/destinations).
4. If the limit is reached, the UI prompts the user to upgrade their plan.

## Epic 3: Signal Processing

### US 3.1: Parse Trading Signals
**As a** system,
**I need to** extract trading parameters from unstructured Telegram messages,
**So that** I can construct a valid JSON payload for SageMaster.

**Acceptance Criteria:**
1. The system listens for new messages in the configured channels.
2. The raw message text is sent to the AI Parsing Engine.
3. The AI extracts: Symbol, Direction (Buy/Sell), Entry Price (optional), Stop Loss (optional), and Take Profit(s) (optional).
4. The parser returns a structured JSON object or Pydantic model.
5. If the message is not a trading signal (e.g., chat, promotion), the parser identifies it as "ignored".

### US 3.2: Dispatch Webhooks (Multi-Destination)
**As a** system,
**I need to** send the parsed signal data to all active destinations configured for the source channel,
**So that** SageMaster can route the orders.

**Acceptance Criteria:**
1. The system retrieves all active `routing_rules` where the Source matches the channel ID.
2. For each rule, the system applies the destination-specific symbol mappings and risk overrides.
3. The system constructs the JSON payload according to the V1 or V2 schema for that specific destination.
4. The system sends an HTTP POST request to each destination's webhook URL.
5. The system logs the raw message, parsed data, payload, and HTTP response status for *each* dispatch in the `signal_logs` table.

## Epic 4: Advanced Configuration

### US 4.1: Destination-Specific Symbol Mapping
**As a** user,
**I want to** map custom symbols used by signal providers to standard broker symbols on a per-destination basis,
**So that** my trades are routed correctly even if different brokers require different symbol suffixes (e.g., "GOLD" to "XAUUSD" for Bot 1, and "GOLD" to "XAUUSD.pro" for Bot 2).

**Acceptance Criteria:**
1. The UI provides a section to define symbol mappings within each Routing Rule.
2. The user can enter a "Provider Symbol" and a "Broker Symbol".
3. The system saves the mappings as a JSON object in the `routing_rules` table.
4. During signal processing, the system replaces the parsed symbol with the mapped symbol specific to that destination before constructing the webhook payload.
