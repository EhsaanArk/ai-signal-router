"""Core signal parsing orchestration.

This module contains the pure domain logic for parsing and validating trading
signals.  It delegates the actual parsing to whatever ``SignalParser``
implementation is injected (e.g. OpenAI adapter, regex adapter).
"""

from __future__ import annotations

from src.core.interfaces import SignalParser
from src.core.models import ParsedSignal, RawSignal


async def parse_and_validate(parser: SignalParser, raw: RawSignal) -> ParsedSignal:
    """Parse a raw signal and validate the result.

    Parameters
    ----------
    parser:
        Any object satisfying the ``SignalParser`` protocol.
    raw:
        The unprocessed signal captured from Telegram.

    Returns
    -------
    ParsedSignal
        The validated, structured signal ready for routing.

    Raises
    ------
    ValueError
        If the parsed signal claims to be valid but is missing required
        fields (``symbol`` or ``direction``).
    """
    parsed = await parser.parse(raw)

    if parsed.is_valid_signal:
        if not parsed.symbol or not parsed.symbol.strip():
            raise ValueError(
                "Parsed signal is marked valid but 'symbol' is missing or empty."
            )
        if not parsed.direction or parsed.direction not in ("long", "short"):
            raise ValueError(
                "Parsed signal is marked valid but 'direction' is missing or "
                f"invalid: {parsed.direction!r}."
            )

    return parsed
