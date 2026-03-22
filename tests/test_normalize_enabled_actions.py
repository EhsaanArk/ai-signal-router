"""Unit tests for normalize_enabled_actions()."""

from src.core.models import (
    ALL_ACTION_VALUES,
    ENTRY_ACTION_VALUES,
    normalize_enabled_actions,
)


class TestNormalizeEnabledActions:
    def test_none_returns_none(self):
        assert normalize_enabled_actions(None) is None

    def test_full_set_collapses_to_none(self):
        assert normalize_enabled_actions(list(ALL_ACTION_VALUES)) is None

    def test_invalid_keys_stripped(self):
        result = normalize_enabled_actions(["bogus_key", "close_order_at_market_price"])
        assert "bogus_key" not in result
        assert "close_order_at_market_price" in result

    def test_entry_actions_always_present(self):
        result = normalize_enabled_actions(["close_order_at_market_price"])
        assert result is not None
        for entry in ENTRY_ACTION_VALUES:
            assert entry in result

    def test_partial_set_preserves_selected(self):
        selected = ["close_order_at_market_price", "move_sl_to_breakeven"]
        result = normalize_enabled_actions(selected)
        assert result is not None
        for key in selected:
            assert key in result

    def test_empty_list_returns_entry_actions_only(self):
        result = normalize_enabled_actions([])
        assert result is not None
        assert set(result) == ENTRY_ACTION_VALUES

    def test_duplicates_deduplicated(self):
        result = normalize_enabled_actions([
            "close_order_at_market_price",
            "close_order_at_market_price",
        ])
        assert result is not None
        assert result.count("close_order_at_market_price") == 1

    def test_all_entry_keys_only_does_not_collapse(self):
        # Only entry keys = not the full set, should return a list
        result = normalize_enabled_actions(list(ENTRY_ACTION_VALUES))
        assert result is not None
        assert set(result) == ENTRY_ACTION_VALUES
