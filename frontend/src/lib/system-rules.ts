/**
 * Static reference data for all hardcoded business rules in the system.
 * Update this file in the same PR when changing backend rules.
 */

export type RuleValue =
  | string
  | string[]
  | Record<string, string | string[]>
  | { headers: string[]; rows: string[][] };

export interface SystemRule {
  key: string;
  label: string;
  description: string;
  value: RuleValue;
}

export interface SystemRuleCategory {
  category: string;
  label: string;
  icon: string; // lucide icon name reference
  description: string;
  rules: SystemRule[];
}

export const SYSTEM_RULES: SystemRuleCategory[] = [
  // ── 1. Tier & Limits ──────────────────────────────────────────────
  {
    category: "tier_limits",
    label: "Tier & Limits",
    icon: "Layers",
    description:
      "Subscription tier caps that limit the number of routing rule destinations a user can create.",
    rules: [
      {
        key: "destination_caps",
        label: "Destination Caps per Tier",
        description:
          "Maximum number of routing rule destinations allowed per subscription tier.",
        value: {
          Free: "1",
          Starter: "2",
          Pro: "5",
          Elite: "15",
        },
      },
    ],
  },

  // ── 2. Signal Processing ──────────────────────────────────────────
  {
    category: "signal_processing",
    label: "Signal Processing",
    icon: "Zap",
    description:
      "Rules governing how incoming signals are parsed, classified, and mapped to webhook action types.",
    rules: [
      {
        key: "forex_action_mappings",
        label: "Forex Action Type Mappings",
        description:
          "How parsed signal actions map to SageMaster webhook action types for forex/commodities/indices destinations.",
        value: {
          headers: ["Signal Action", "Webhook Action Type"],
          rows: [
            ["entry (long)", "start_long_market_deal"],
            ["entry (short)", "start_short_market_deal"],
            ["partial_close (percentage)", "partially_close_by_percentage"],
            ["partial_close (lots)", "partially_close_by_lot"],
            ["breakeven", "move_sl_to_breakeven"],
            ["close_position", "close_order_at_market_price"],
            ["modify_tp", "Not supported (raises error)"],
          ],
        },
      },
      {
        key: "crypto_action_mappings",
        label: "Crypto Action Type Mappings",
        description:
          "How parsed signal actions map to SageMaster webhook action types for crypto destinations.",
        value: {
          headers: ["Signal Action", "Webhook Action Type"],
          rows: [
            ["start_deal", "start_deal"],
            ["close_position", "close_order_at_market_price"],
            ["partial_close (lot)", "partially_closed_by_percentage"],
            ["partial_close (percentage)", "partially_closed_by_percentage"],
            ["breakeven", "moved_sl_adjustment"],
          ],
        },
      },
      {
        key: "action_priority",
        label: "Action Priority Order",
        description:
          "When multiple actions are detected in a single message, the highest-priority action is selected. Entry signals are never combined with follow-up actions.",
        value: [
          "1. close_position (highest — irreversible)",
          "2. partial_close (reduces exposure)",
          "3. breakeven (protects capital)",
          "4. trailing_sl (dynamic risk)",
          "5. modify_sl (risk adjustment)",
          "6. modify_tp (lowest priority)",
        ],
      },
      {
        key: "partial_close_defaults",
        label: "Partial Close Defaults",
        description:
          'Default behavior when a partial close signal does not specify an amount.',
        value: [
          'Default percentage: 50% when unspecified or "half" is mentioned',
          "Preference: percentage over lots when ambiguous",
          "If lot size is explicitly stated, lots field is used instead",
        ],
      },
      {
        key: "symbol_normalization",
        label: "Symbol Normalization",
        description:
          "The LLM normalizes common symbol aliases to canonical forms and classifies asset classes.",
        value: {
          headers: ["Input Aliases", "Normalized Symbol", "Asset Class"],
          rows: [
            ["GOLD, XAUUSD, Gold", "XAUUSD", "commodities"],
            ["SILVER, XAGUSD", "XAGUSD", "commodities"],
            ["BTC, BTCUSD, BTC/USD, Bitcoin", "BTC/USD", "crypto"],
            ["ETH, ETHUSD, ETH/USD, Ethereum", "ETH/USD", "crypto"],
            ["US30, NAS100, SPX500, DAX, USTEC", "(preserved)", "indices"],
            ["(anything else)", "(preserved)", "forex (default)"],
          ],
        },
      },
      {
        key: "signal_validation",
        label: "Signal Validation",
        description:
          "Minimum requirements for a signal to be considered valid and dispatched.",
        value: [
          "symbol must be non-empty",
          'direction must be "long" or "short"',
          "Invalid signals are logged with status ignored and the ignore reason",
        ],
      },
    ],
  },

  // ── 3. Pre-Dispatch Filters ───────────────────────────────────────
  {
    category: "pre_dispatch_filters",
    label: "Pre-Dispatch Filters",
    icon: "Filter",
    description:
      "Four cascading filters applied in order before a signal is dispatched to a destination. If any filter rejects the signal, dispatch is skipped for that rule.",
    rules: [
      {
        key: "filter_1_keyword_blacklist",
        label: "1. Keyword Blacklist",
        description:
          "If the routing rule has a keyword_blacklist, the raw message is checked (case-insensitive). Any match causes the signal to be ignored for that rule.",
        value: 'Error: "Message contains blacklisted keyword \'{keyword}\'"',
      },
      {
        key: "filter_2_enabled_actions",
        label: "2. Enabled Actions",
        description:
          "If the routing rule has enabled_actions set, only those actions are allowed. Unsupported actions (e.g., modify_tp) are also rejected here.",
        value: 'Error: "Action \'{action}\' is disabled for this route"',
      },
      {
        key: "filter_3_symbol_mismatch",
        label: "3. Symbol Mismatch",
        description:
          "If the routing rule template has a hardcoded symbol (no {{ticker}} placeholder), the signal symbol must match it exactly.",
        value:
          "Hardcoded template symbol = non-empty string without {{...}} placeholder. Mismatch causes signal to be ignored.",
      },
      {
        key: "filter_4_asset_class",
        label: "4. Asset Class Compatibility",
        description:
          "The signal's asset class must be compatible with the destination type.",
        value: {
          sagemaster_forex: ["forex", "commodities", "indices"],
          sagemaster_crypto: ["crypto"],
          custom: ["all (no restrictions)"],
        },
      },
    ],
  },

  // ── 4. Payload & Dispatch ─────────────────────────────────────────
  {
    category: "payload_dispatch",
    label: "Payload & Dispatch",
    icon: "Send",
    description:
      "Rules for building webhook payloads, handling retries, and dispatching to destinations.",
    rules: [
      {
        key: "entry_only_fields",
        label: "Entry-Only Fields",
        description:
          "These fields are stripped from management action payloads (partial_close, breakeven, close_position, modify_sl, trailing_sl). They only appear in entry payloads.",
        value: ["price", "takeProfits", "stopLoss", "balance"],
      },
      {
        key: "template_placeholders",
        label: "Template Placeholders",
        description:
          "TradingView-style placeholders that are replaced in the webhook payload template before dispatch.",
        value: {
          "{{time}}": "UTC timestamp (e.g., 2026-03-13T21:19:00Z)",
          "{{close}}": "Signal entry price (empty string if null)",
          "{{ticker}}": "Signal symbol",
        },
      },
      {
        key: "crypto_specific",
        label: "Crypto-Specific Field Mappings",
        description:
          "Crypto destinations use different field names and behaviors compared to forex.",
        value: [
          "Partial close: uses percentage field + position_type (no lot-based)",
          "SL adjustment: uses sl_adjustment (snake_case, not slAdjustment)",
          "position_type is required for partial_close and SL adjustment",
          'position_type defaults to signal.direction or "long"',
        ],
      },
      {
        key: "payload_versions",
        label: "Payload V1 vs V2",
        description:
          "Two payload versions with different field support.",
        value: {
          headers: ["Feature", "V1 (Strategy Trigger)", "V2 (Trade Signal)"],
          rows: [
            ["Basic fields", "type, assistId, source, symbol, date", "Same"],
            ["Management fields", "slAdjustment, percentage, lotSize", "Same"],
            ["Entry fields", "Not supported", "price, takeProfits, stopLoss, lots"],
            ["Fill behavior", "—", "Only fills if template key exists with empty value"],
          ],
        },
      },
      {
        key: "risk_overrides",
        label: "Risk Override Merging",
        description:
          "Order of precedence when building the final webhook payload.",
        value: [
          "1. Build payload from template",
          "2. Apply symbol mapping",
          "3. Merge risk_overrides (overwrites template values — highest precedence)",
        ],
      },
      {
        key: "webhook_retry",
        label: "Webhook Retry Logic",
        description:
          "Retry strategy for failed webhook deliveries.",
        value: {
          "Max retries": "3 attempts",
          "Base delay": "0.5 seconds",
          "Backoff": "Exponential: 0.5 * 2^attempt + random(0, 0.25)s",
          "Retryable codes": "429, 500, 502, 503, 504",
          "Timeout": "15 seconds per attempt",
          "Non-retryable": "4xx errors fail immediately",
        },
      },
      {
        key: "dispatch_concurrency",
        label: "Dispatch Concurrency",
        description:
          "How signals are dispatched to multiple destinations.",
        value: [
          "All rules dispatched in parallel via asyncio.gather()",
          "DB writes are sequential (AsyncSession not safe for concurrent writes)",
          "All dispatch outcomes are logged to signal_logs table",
        ],
      },
    ],
  },

  // ── 5. Notifications ──────────────────────────────────────────────
  {
    category: "notifications",
    label: "Notifications",
    icon: "Bell",
    description:
      "Conditions under which email and Telegram notifications are sent after signal processing.",
    rules: [
      {
        key: "email_notifications",
        label: "Email Notification Conditions",
        description:
          "When email notifications are triggered after processing a signal.",
        value: [
          "Sent when email_on_failure is enabled AND there are failures",
          "Sent when email_on_success is enabled AND there are successes",
          "Requires RESEND_API_KEY to be configured",
        ],
      },
      {
        key: "telegram_notifications",
        label: "Telegram Notification Conditions",
        description:
          "When Telegram bot notifications are triggered after processing a signal.",
        value: [
          "Sent when telegram_on_failure is enabled AND there are failures",
          "Sent when telegram_on_success is enabled AND there are successes",
          "Requires telegram_bot_chat_id to be set in user preferences",
          "Requires TELEGRAM_BOT_TOKEN to be configured",
        ],
      },
    ],
  },

  // ── 6. Security & Config ──────────────────────────────────────────
  {
    category: "security_config",
    label: "Security & Config",
    icon: "Shield",
    description:
      "Authentication, encryption, and infrastructure security settings.",
    rules: [
      {
        key: "jwt_config",
        label: "JWT Configuration",
        description: "JSON Web Token settings for user authentication.",
        value: {
          Algorithm: "HS256",
          "Token expiry": "7 days",
        },
      },
      {
        key: "encryption",
        label: "Encryption",
        description:
          "Encryption settings for sensitive data (Telegram session strings, API keys).",
        value: {
          Cipher: "AES-256-GCM",
          "Nonce size": "12 bytes (96-bit)",
          "Legacy support": "Fernet decryption for migration",
        },
      },
      {
        key: "cors",
        label: "CORS Configuration",
        description: "Cross-Origin Resource Sharing policy.",
        value: {
          headers: ["Setting", "Development", "Production"],
          rows: [
            ["Allowed origins", "localhost:5173, localhost:3000", "FRONTEND_URL only"],
            ["Methods", "GET, POST, PUT, DELETE, OPTIONS", "Same"],
            ["Headers", "Content-Type, Authorization", "Same"],
            ["Credentials", "Allowed", "Allowed"],
          ],
        },
      },
      {
        key: "security_headers",
        label: "Security Headers",
        description: "HTTP security headers applied to all responses.",
        value: {
          "X-Content-Type-Options": "nosniff",
          "X-Frame-Options": "DENY",
          "Referrer-Policy": "strict-origin-when-cross-origin",
          "Strict-Transport-Security": "max-age=31536000; includeSubDomains (production only)",
        },
      },
      {
        key: "production_validation",
        label: "Production Startup Validation",
        description:
          "Required configuration checks when LOCAL_MODE=false. Server refuses to start if any check fails.",
        value: [
          "JWT_SECRET_KEY must not be the default dev value",
          "ENCRYPTION_KEY must be non-empty",
          "OPENAI_API_KEY must be non-empty",
          "DATABASE_URL must not contain localhost",
          "REDIS_URL must not contain localhost",
          "FRONTEND_URL must be set (not localhost)",
          "TELEGRAM_API_ID must be > 0",
        ],
      },
    ],
  },
];
