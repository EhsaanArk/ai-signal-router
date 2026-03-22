export type ImpactLevel = "entry" | "risk-management" | "increases-exposure" | "high-impact" | "operational";

export interface ActionDefinition {
  key: string;
  label: string;
  description: string;
  example: string;
  /** Multiple example messages that signal providers commonly use. */
  examples: { forex: string[]; crypto: string[] };
  /** Impact level from a retail trader's perspective. */
  impact: ImpactLevel;
  /** When this action is typically sent in a trading context. */
  scenario: string;
  /** What happens when this webhook is dispatched. */
  effect: string;
  /** V1 payload version overrides for entry actions (forex only). */
  v1?: { description: string; scenario: string; effect: string };
  isEntry?: boolean;
  forexOnly?: boolean;
  cryptoOnly?: boolean;
}

// Keep isEntry flags in sync with backend: src/core/models.py (ENTRY_ACTION_VALUES).
export const ACTION_DEFINITIONS: ActionDefinition[] = [
  {
    key: "start_long_market_deal",
    label: "Entry Long",
    description: "Dispatch a long/buy entry webhook with optional SL and TP",
    example: '"Buy EURUSD at market"',
    examples: {
      forex: ["Buy EURUSD at market", "XAUUSD BUY 2340 SL 2320 TP 2380", "Long GBPUSD SL 50 pips TP 100 pips", "GOLD BUY entry 2350"],
      crypto: ["Buy BTC/USDT at market", "BTC LONG 62000 SL 60000 TP 65000", "Long ETH SL 5% TP 10%", "Enter BTC buy 61500 SL 60000 TP 65000"],
    },
    impact: "entry",
    scenario: "Signal provider identifies a buying opportunity and sends an entry call. SL and TP levels are included when the provider specifies them.",
    effect: "Dispatches a webhook with the entry details, including any SL/TP levels detected in the message. Your connected platform handles the order.",
    v1: {
      description: "Dispatch a long/buy entry signal — SL/TP use your strategy config",
      scenario: "Signal provider identifies a buying opportunity. With V1, SL and TP from the message are not forwarded — your platform strategy settings apply.",
      effect: "Dispatches an entry-only webhook (symbol + direction). SL, TP, lot size, and risk management all come from your strategy configuration on your connected platform.",
    },
    isEntry: true,
  },
  {
    key: "start_short_market_deal",
    label: "Entry Short",
    description: "Dispatch a short/sell entry webhook with optional SL and TP",
    example: '"Sell GBPUSD at market"',
    examples: {
      forex: ["Sell GBPUSD at market", "EURUSD SELL 1.0850 SL 1.0900 TP 1.0750", "Short XAUUSD SL 2400 TP 2280", "GOLD SELL now"],
      crypto: ["Sell ETH/USDT at market", "BTC SHORT 63000 SL 65000 TP 58000", "Short SOL SL 5% TP 15%", "ETH sell 3200 SL 3300 TP 2900"],
    },
    impact: "entry",
    scenario: "Signal provider spots a bearish setup and sends a sell/short entry signal. SL and TP levels are included when the provider specifies them.",
    effect: "Dispatches a webhook with the entry details, including any SL/TP levels detected in the message. Your connected platform handles the order.",
    v1: {
      description: "Dispatch a short/sell entry signal — SL/TP use your strategy config",
      scenario: "Signal provider spots a bearish setup. With V1, SL and TP from the message are not forwarded — your platform strategy settings apply.",
      effect: "Dispatches an entry-only webhook (symbol + direction). SL, TP, lot size, and risk management all come from your strategy configuration on your connected platform.",
    },
    isEntry: true,
  },
  {
    key: "start_long_limit_deal",
    label: "Entry Long (Limit)",
    description: "Dispatch a buy limit order webhook with optional SL and TP",
    example: '"Buy limit EURUSD @ 1.0950"',
    examples: {
      forex: ["Buy limit EURUSD @ 1.0950", "XAUUSD buy limit 2300 SL 2280 TP 2350", "Place buy order GBPUSD at 1.2500"],
      crypto: ["Buy limit BTC/USDT @ 60000", "BTC limit long 58000 SL 56000 TP 64000", "Set buy order ETH at 2800"],
    },
    impact: "entry",
    scenario: "Provider wants to enter at a better price. The order waits until price reaches the limit level. SL and TP are included when specified.",
    effect: "Dispatches a webhook for a pending buy limit order with any SL/TP levels. Your connected platform places the order at the specified price.",
    v1: {
      description: "Dispatch a buy limit signal — SL/TP use your strategy config",
      scenario: "Provider wants to enter at a better price. With V1, SL and TP from the message are not forwarded — your platform strategy settings apply.",
      effect: "Dispatches an entry-only webhook (symbol + limit price). SL, TP, lot size, and risk management all come from your strategy configuration on your connected platform.",
    },
    isEntry: true,
  },
  {
    key: "start_short_limit_deal",
    label: "Entry Short (Limit)",
    description: "Dispatch a sell limit order webhook with optional SL and TP",
    example: '"Sell limit GBPUSD @ 1.2500"',
    examples: {
      forex: ["Sell limit GBPUSD @ 1.2500", "XAUUSD sell limit 2400 SL 2420 TP 2350", "Place sell order EURUSD at 1.1000"],
      crypto: ["Sell limit ETH/USDT @ 3200", "BTC limit short 65000 SL 67000 TP 60000", "Set sell order SOL at 200"],
    },
    impact: "entry",
    scenario: "Provider expects price to rise to a resistance level before selling. SL and TP are included when specified.",
    effect: "Dispatches a webhook for a pending sell limit order with any SL/TP levels. Your connected platform places the order at the specified price.",
    v1: {
      description: "Dispatch a sell limit signal — SL/TP use your strategy config",
      scenario: "Provider expects price to rise before selling. With V1, SL and TP from the message are not forwarded — your platform strategy settings apply.",
      effect: "Dispatches an entry-only webhook (symbol + limit price). SL, TP, lot size, and risk management all come from your strategy configuration on your connected platform.",
    },
    isEntry: true,
  },
  {
    key: "close_order_at_market_price",
    label: "Close Position",
    description: "Dispatch a close position webhook for a specific symbol",
    example: '"Close all", "Exit trade"',
    examples: {
      forex: ["Close XAUUSD", "Exit EURUSD trade", "Close gold position", "Take profit on GBPUSD"],
      crypto: ["Close BTC position", "Exit ETH trade", "Close BTC/USDT", "TP hit, closing SOL"],
    },
    impact: "high-impact",
    scenario: "Trade has hit its target, or the provider wants to exit before a news event.",
    effect: "Dispatches a webhook instructing your connected platform to close the position for the specified symbol at market price.",
  },
  {
    key: "partially_close_by_percentage",
    label: "Partial Close (%)",
    description: "Dispatch a partial close webhook by percentage",
    example: '"Close 50%", "Take half off"',
    examples: {
      forex: ["Close 50%", "Take half off XAUUSD", "Secure 50% profit", "Partial close 75%", "Close 30% of position"],
      crypto: ["Close 50% BTC", "Take 25% profit", "Partial close 50%", "Secure half off ETH"],
    },
    impact: "risk-management",
    scenario: "Price is moving in your favor. Provider locks in partial profit while letting the rest run for a bigger target.",
    effect: "Dispatches a webhook to close the specified percentage of the position. Your connected platform handles the partial close.",
  },
  {
    key: "partially_close_by_lot",
    label: "Partial Close (Lots)",
    description: "Dispatch a partial close webhook by lot size",
    example: '"Close 0.5 lots"',
    examples: {
      forex: ["Close 0.5 lots", "Close 1 lot EURUSD", "Take 0.3 lots off XAUUSD", "Reduce by 0.5 lots"],
      crypto: [],
    },
    impact: "risk-management",
    scenario: "Provider wants precise control over how much to close, specifying exact lot size rather than a percentage.",
    effect: "Dispatches a webhook to close the specified lot amount. Only available for forex-compatible destinations.",
    forexOnly: true,
  },
  {
    key: "move_sl_to_breakeven",
    label: "Breakeven / Move SL",
    description: "Dispatch a webhook to move stop loss — breakeven, trailing SL, or custom SL level",
    example: '"Move SL to BE", "Breakeven"',
    examples: {
      forex: ["Move SL to BE", "Breakeven XAUUSD", "Move SL to 2350", "Trail SL 20 pips", "Secure entry on gold", "BE on EURUSD"],
      crypto: ["Breakeven BTC", "Move SL to entry", "Move SL to 61000", "Trail stop 3%", "Secure BTC position"],
    },
    impact: "risk-management",
    scenario: "Trade is in profit. Provider adjusts the stop loss — either to breakeven (entry price), a specific price level, or a trailing offset. All SL modifications route through this action.",
    effect: "Dispatches a webhook instructing your connected platform to adjust the stop loss. Supports breakeven, custom SL price, and trailing SL offsets.",
  },
  {
    key: "open_extra_order",
    label: "Add Funds / Extra Order",
    description: "Dispatch a webhook to add funds or DCA into an existing position",
    example: '"Add funds", "DCA", "Average down"',
    examples: {
      forex: [],
      crypto: ["Add funds BTC", "DCA into ETH", "Average down on SOL", "Add to BTC position", "Double down on ETH"],
    },
    impact: "increases-exposure",
    scenario: "Price has moved against the position. Provider dollar-cost-averages (DCA) by adding more funds to lower the average entry.",
    effect: "Dispatches a webhook to add funds or place an additional order. Your connected platform handles the execution.",
    cryptoOnly: true,
  },
  {
    key: "close_all_orders_at_market_price",
    label: "Close All Positions",
    description: "Dispatch a webhook to close every open trade across all symbols",
    example: '"Close all trades", "Flatten everything"',
    examples: {
      forex: ["Close all trades", "Flatten everything", "Close all positions now", "Exit all", "Liquidate everything"],
      crypto: ["Close all deals", "Exit everything", "Flatten all", "Close all crypto positions"],
    },
    impact: "high-impact",
    scenario: "Major market event (NFP, CPI, black swan). Provider wants to exit ALL positions immediately regardless of P&L.",
    effect: "Dispatches a webhook instructing your connected platform to close all open positions across all symbols at market price.",
  },
  {
    key: "close_all_orders_at_market_price_and_stop_assist",
    label: "Close All & Stop",
    description: "Dispatch a webhook to close all positions and stop the Assist",
    example: '"Close all and stop", "Emergency stop"',
    examples: {
      forex: ["Close all and stop", "Emergency stop", "Shut everything down", "Kill all and stop bot"],
      crypto: ["Close all and stop AI", "Emergency shutdown", "Stop everything now"],
    },
    impact: "high-impact",
    scenario: "Critical situation — provider wants to exit all positions AND prevent the Assist from accepting new signals.",
    effect: "Dispatches a webhook to close all positions and stop the Assist. Your connected platform handles both actions.",
  },
  {
    key: "start_assist",
    label: "Start Assist",
    description: "Dispatch a webhook to resume the Assist",
    example: '"Start the Assist", "Resume trading"',
    examples: {
      forex: ["Start the bot", "Resume trading", "Turn on the assist", "Start copying signals again"],
      crypto: ["Start AI assist", "Resume the bot", "Turn on trading", "Reactivate assist"],
    },
    impact: "operational",
    scenario: "After a pause (weekend, news event, or manual stop), the provider resumes signal copying.",
    effect: "Dispatches a webhook to resume the Assist on your connected platform. New incoming signals will be forwarded again.",
  },
  {
    key: "stop_assist",
    label: "Stop Assist",
    description: "Dispatch a webhook to pause the Assist",
    example: '"Stop the Assist", "Pause trading"',
    examples: {
      forex: ["Stop the bot", "Pause trading", "Turn off assist", "Stop copying", "Hold off on new trades"],
      crypto: ["Stop AI assist", "Pause the bot", "Turn off trading", "No new trades"],
    },
    impact: "operational",
    scenario: "Upcoming high-impact news, weekend, or uncertainty. Provider pauses to prevent new entries while keeping existing positions.",
    effect: "Dispatches a webhook to pause the Assist on your connected platform. No new webhooks will be forwarded until resumed.",
  },
];

const ENTRY_ONLY_FIELDS = ["price", "takeProfits", "takeProfitsPips", "stopLoss", "stopLossPips", "balance"];

export function generateActionPreview(
  actionKey: string,
  template: Record<string, unknown> | null | undefined,
): string {
  if (!template) return "No template configured";

  // Clone template
  const payload: Record<string, unknown> = { ...template };

  // Replace placeholders
  payload["type"] = actionKey;
  for (const [key, value] of Object.entries(payload)) {
    if (typeof value === "string") {
      payload[key] = value
        .replace("{{ticker}}", "EURUSD")
        .replace("{{close}}", "1.1234")
        .replace("{{time}}", new Date().toISOString().replace(/\.\d{3}Z$/, "Z"));
    }
  }

  // For non-entry actions, strip entry-only fields and inject action-specific fields
  // Use the ACTION_DEFINITIONS isEntry flag — not string prefix matching
  // (start_assist starts with "start_" but is NOT an entry action)
  const entryKeys = new Set(ACTION_DEFINITIONS.filter((a) => a.isEntry).map((a) => a.key));
  const isEntry = entryKeys.has(actionKey);
  if (!isEntry) {
    for (const field of ENTRY_ONLY_FIELDS) {
      delete payload[field];
    }
    // Also strip lots from entry template
    delete payload["lots"];

    if (actionKey === "partially_close_by_lot") {
      payload["lotSize"] = "0.5";
    } else if (
      actionKey === "partially_close_by_percentage" ||
      actionKey === "partially_closed_by_percentage"
    ) {
      payload["percentage"] = 50;
    } else if (actionKey === "move_sl_to_breakeven" || actionKey === "moved_sl_adjustment") {
      payload["slAdjustment"] = 0;
      payload["sl_adjustment"] = 0;
    } else if (actionKey === "open_extra_order") {
      payload["is_market"] = true;
      payload["position_type"] = "long";
    }

    // Symbol-less actions: strip symbol fields
    const SYMBOLLESS = ["close_all_orders_at_market_price", "close_all_orders_at_market_price_and_stop_assist", "start_assist", "stop_assist"];
    if (SYMBOLLESS.includes(actionKey)) {
      delete payload["symbol"];
      delete payload["tradeSymbol"];
      delete payload["eventSymbol"];
    }
  } else {
    // For entry, fill empty fields with example values
    if (payload["symbol"] === "") payload["symbol"] = "EURUSD";
    if (payload["source"] === "") payload["source"] = "forex";
    if (payload["date"] === "") {
      payload["date"] = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
    }
  }

  return JSON.stringify(payload, null, 2);
}

/** Crypto-specific example overrides for actions whose examples reference forex symbols. */
const CRYPTO_EXAMPLES: Partial<Record<string, string>> = {
  start_long_market_deal: '"Buy BTC/USDT at market"',
  start_short_market_deal: '"Sell ETH/USDT at market"',
  start_long_limit_deal: '"Buy limit BTC/USDT @ 60000"',
  start_short_limit_deal: '"Sell limit ETH/USDT @ 3200"',
};

/** Return the action definitions filtered for a destination type. */
export function getActionsForDestination(
  destinationType: string,
): ActionDefinition[] {
  return ACTION_DEFINITIONS.filter((a) => {
    if (a.forexOnly && destinationType !== "sagemaster_forex") return false;
    if (a.cryptoOnly && destinationType !== "sagemaster_crypto") return false;
    return true;
  });
}

/**
 * Return action definitions with destination-aware examples.
 * Crypto destinations get crypto-style example text.
 */
export function getActionExamples(
  destinationType: string,
): ActionDefinition[] {
  const actions = getActionsForDestination(destinationType);
  if (destinationType !== "sagemaster_crypto") return actions;
  return actions.map((a) => {
    const override = CRYPTO_EXAMPLES[a.key];
    return override ? { ...a, example: override } : a;
  });
}

/** Return all action keys (for initializing enabled_actions). */
export function getAllActionKeys(destinationType: string): string[] {
  return getActionsForDestination(destinationType).map((a) => a.key);
}

/** Get the example messages appropriate for a destination type. */
export function getExamplesForDestination(
  action: ActionDefinition,
  destinationType: string,
): string[] {
  const list = destinationType === "sagemaster_crypto" ? action.examples.crypto : action.examples.forex;
  return list.length > 0 ? list : (destinationType === "sagemaster_crypto" ? action.examples.forex : action.examples.crypto);
}

/** Impact level display config. */
export const IMPACT_CONFIG: Record<ImpactLevel, { label: string; color: string; bg: string; border: string }> = {
  "entry": { label: "Entry", color: "text-emerald-500", bg: "bg-emerald-500/10", border: "border-emerald-500/20" },
  "risk-management": { label: "Risk Management", color: "text-sky-500", bg: "bg-sky-500/10", border: "border-sky-500/20" },
  "increases-exposure": { label: "Increases Exposure", color: "text-amber-500", bg: "bg-amber-500/10", border: "border-amber-500/20" },
  "high-impact": { label: "High Impact", color: "text-red-500", bg: "bg-red-500/10", border: "border-red-500/20" },
  "operational": { label: "Operational", color: "text-muted-foreground", bg: "bg-muted/50", border: "border-border" },
};

/**
 * Return the normalised enabled_actions for a destination.
 * If null/undefined (= all enabled), returns every key for the destination.
 * Filters out keys that don't apply to the destination type.
 */
export function getNormalizedEnabledActions(
  enabledActions: string[] | null | undefined,
  destinationType: string,
): string[] {
  const allKeys = getAllActionKeys(destinationType);
  if (!enabledActions) return allKeys;
  const validSet = new Set(allKeys);
  return enabledActions.filter((k) => validSet.has(k));
}

/** Actions not supported by SageMaster, shown in the Command Reference for clarity. */
export interface UnsupportedAction {
  label: string;
  reason: string;
  /** Only shown for specific destination types. Omit = shown for all SageMaster. */
  destinationType?: string;
}

export const UNSUPPORTED_ACTIONS: UnsupportedAction[] = [
  {
    label: "Modify TP on existing trade",
    reason: "Not supported via webhook — TP can only be set at entry time",
  },
  {
    label: "Set SL to absolute price (crypto)",
    reason: "Crypto destinations only support relative SL offsets, not absolute price levels",
    destinationType: "sagemaster_crypto",
  },
];

/** Get unsupported actions filtered for a destination type. */
export function getUnsupportedForDestination(
  destinationType: string,
): UnsupportedAction[] {
  return UNSUPPORTED_ACTIONS.filter(
    (a) => !a.destinationType || a.destinationType === destinationType,
  );
}

/** Compute badge label: "8/12" for enabled vs total actions. */
export function getActionBadge(
  enabledActions: string[] | null,
  destinationType: string,
): string {
  const total = getActionsForDestination(destinationType).length;
  const enabled = enabledActions ? enabledActions.length : total;
  return `${enabled}/${total}`;
}
