"""Centralised constants for the SGM Telegram Signal Copier.

All magic numbers and configuration defaults live here so they are
discoverable from a single file.
"""

# -- Webhook dispatch ------------------------------------------------
WEBHOOK_MAX_RETRIES: int = 3
WEBHOOK_RETRY_BASE_DELAY: float = 0.5  # seconds
WEBHOOK_TIMEOUT: float = 15.0  # seconds
RETRYABLE_HTTP_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# -- Cache TTLs ------------------------------------------------------
USER_CACHE_TTL_SECONDS: int = 300  # 5 minutes
SESSION_CACHE_TTL_SECONDS: int = 60 * 60 * 24  # 24 hours
PARSER_CONFIG_CACHE_TTL_SECONDS: int = 300  # 5 minutes

# -- Auth tokens -----------------------------------------------------
ACCESS_TOKEN_EXPIRE_DAYS: int = 7

# -- DNS / Security --------------------------------------------------
DNS_TIMEOUT_SECONDS: float = 2.0
DNS_RESOLVER_POOL_MAX_WORKERS: int = 4

# -- Terms of Service ------------------------------------------------
CURRENT_TOS_VERSION: str = "2026-03-22"  # Update when ToS/Privacy changes

# -- Beta lockdown ----------------------------------------------------
ACCOUNT_DISABLED_MSG: str = (
    "Thanks for being part of the beta program! "
    "We are working towards the big launch — stay tuned!"
)

# -- Legacy -----------------------------------------------------------
LEGACY_TOKEN_SCAN_LIMIT: int = 500
