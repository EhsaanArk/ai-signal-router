import type { DestinationType } from "@/types/api";

export interface ActionExample {
  label: string;
  text: string;
}

export interface ActionDefinition {
  key: string;
  label: string;
  description: string;
  example: string;
  category: "entries" | "management";
  required?: boolean;
  examplesByDestination?: Partial<Record<DestinationType, ActionExample[]>>;
  isEntry?: boolean;
  forexOnly?: boolean;
  cryptoOnly?: boolean;
}

export const ACTION_DEFINITIONS: ActionDefinition[] = [
  {
    key: "start_long_market_deal",
    label: "Entry Long",
    description: "Open a new long/buy position",
    example: '"Buy EURUSD at market"',
    category: "entries",
    required: true,
    examplesByDestination: {
      sagemaster_forex: [
        { label: "Buy EURUSD", text: "Buy EURUSD at market" },
        { label: "Buy XAUUSD", text: "Buy XAUUSD SL 2300 TP 2350" },
      ],
      sagemaster_crypto: [
        { label: "Buy BTC/USDT", text: "Buy BTC/USDT" },
        { label: "Buy ETH/USDT", text: "Buy ETH/USDT TP 4200" },
      ],
    },
    isEntry: true,
  },
  {
    key: "start_short_market_deal",
    label: "Entry Short",
    description: "Open a new short/sell position",
    example: '"Sell GBPUSD at market"',
    category: "entries",
    required: true,
    examplesByDestination: {
      sagemaster_forex: [
        { label: "Sell GBPUSD", text: "Sell GBPUSD at market" },
        { label: "Sell NAS100", text: "Sell NAS100 SL 18800 TP 18500" },
      ],
      sagemaster_crypto: [
        { label: "Sell BTC/USDT", text: "Sell BTC/USDT" },
        { label: "Sell SOL/USDT", text: "Sell SOL/USDT TP 120" },
      ],
    },
    isEntry: true,
  },
  {
    key: "start_long_limit_deal",
    label: "Entry Long (Limit)",
    description: "Open a new long/buy limit order",
    example: '"Buy limit EURUSD @ 1.0950"',
    category: "entries",
    required: true,
    examplesByDestination: {
      sagemaster_forex: [
        { label: "Buy limit EURUSD", text: "Buy limit EURUSD @ 1.0950" },
        { label: "Buy limit XAUUSD", text: "Buy limit XAUUSD @ 2305" },
      ],
      sagemaster_crypto: [
        { label: "Buy limit BTC/USDT", text: "Buy limit BTC/USDT @ 65000" },
        { label: "Buy limit ETH/USDT", text: "Buy limit ETH/USDT @ 3950" },
      ],
    },
    isEntry: true,
  },
  {
    key: "start_short_limit_deal",
    label: "Entry Short (Limit)",
    description: "Open a new short/sell limit order",
    example: '"Sell limit GBPUSD @ 1.2500"',
    category: "entries",
    required: true,
    examplesByDestination: {
      sagemaster_forex: [
        { label: "Sell limit GBPUSD", text: "Sell limit GBPUSD @ 1.2500" },
        { label: "Sell limit XAUUSD", text: "Sell limit XAUUSD @ 2390" },
      ],
      sagemaster_crypto: [
        { label: "Sell limit BTC/USDT", text: "Sell limit BTC/USDT @ 69000" },
        { label: "Sell limit SOL/USDT", text: "Sell limit SOL/USDT @ 155" },
      ],
    },
    isEntry: true,
  },
  {
    key: "close_order_at_market_price",
    label: "Close Position",
    description: "Fully close an open trade",
    example: '"Close all", "Exit trade"',
    category: "management",
    examplesByDestination: {
      sagemaster_forex: [
        { label: "Close EURUSD", text: "Close EURUSD" },
        { label: "Exit trade", text: "Exit trade" },
      ],
      sagemaster_crypto: [
        { label: "Close BTC/USDT", text: "Close BTC/USDT" },
        { label: "Exit trade", text: "Exit trade" },
      ],
    },
  },
  {
    key: "partially_close_by_percentage",
    label: "Partial Close (%)",
    description: "Close a percentage of position",
    example: '"Close 50%", "Take half off"',
    category: "management",
    examplesByDestination: {
      sagemaster_forex: [
        { label: "Close 50%", text: "Close 50%" },
        { label: "Take half off", text: "Take half off" },
      ],
      sagemaster_crypto: [
        { label: "Close 50%", text: "Close 50%" },
        { label: "Close 25%", text: "Close 25%" },
      ],
    },
  },
  {
    key: "partially_close_by_lot",
    label: "Partial Close (Lots)",
    description: "Close a specific lot amount",
    example: '"Close 0.5 lots"',
    category: "management",
    examplesByDestination: {
      sagemaster_forex: [
        { label: "Close 0.5 lots", text: "Close 0.5 lots" },
      ],
    },
    forexOnly: true,
  },
  {
    key: "move_sl_to_breakeven",
    label: "Breakeven",
    description: "Move stop loss to entry price",
    example: '"Move SL to BE", "Breakeven"',
    category: "management",
    examplesByDestination: {
      sagemaster_forex: [
        { label: "Move SL to BE", text: "Move SL to BE" },
        { label: "Breakeven", text: "Breakeven" },
      ],
      sagemaster_crypto: [
        { label: "Move SL to BE", text: "Move SL to BE" },
        { label: "Breakeven", text: "Breakeven" },
      ],
    },
  },
  {
    key: "open_extra_order",
    label: "Add Funds / Extra Order",
    description: "Add funds or place an additional order on an existing position",
    example: '"Add funds", "DCA", "Average down"',
    category: "management",
    examplesByDestination: {
      sagemaster_crypto: [
        { label: "Add funds", text: "Add funds" },
        { label: "DCA", text: "DCA" },
      ],
    },
    cryptoOnly: true,
  },
  {
    key: "close_all_orders_at_market_price",
    label: "Close All Positions",
    description: "Close every open trade across all symbols",
    example: '"Close all trades", "Flatten everything"',
    category: "management",
    examplesByDestination: {
      sagemaster_forex: [
        { label: "Close all trades", text: "Close all trades" },
        { label: "Flatten", text: "Flatten everything" },
      ],
      sagemaster_crypto: [
        { label: "Close all trades", text: "Close all trades" },
        { label: "Flatten", text: "Flatten everything" },
      ],
    },
  },
  {
    key: "close_all_orders_at_market_price_and_stop_assist",
    label: "Close All & Stop",
    description: "Close all positions and stop the Assist",
    example: '"Close all and stop", "Emergency stop"',
    category: "management",
    examplesByDestination: {
      sagemaster_forex: [
        { label: "Close all and stop", text: "Close all and stop" },
        { label: "Emergency stop", text: "Emergency stop" },
      ],
      sagemaster_crypto: [
        { label: "Close all and stop", text: "Close all and stop" },
        { label: "Emergency stop", text: "Emergency stop" },
      ],
    },
  },
  {
    key: "start_assist",
    label: "Start Assist",
    description: "Resume a paused Assist (allows new trades)",
    example: '"Start the bot", "Resume trading"',
    category: "management",
    examplesByDestination: {
      sagemaster_forex: [
        { label: "Start the bot", text: "Start the bot" },
        { label: "Resume trading", text: "Resume trading" },
      ],
      sagemaster_crypto: [
        { label: "Start the bot", text: "Start the bot" },
        { label: "Resume trading", text: "Resume trading" },
      ],
    },
  },
  {
    key: "stop_assist",
    label: "Stop Assist",
    description: "Pause the Assist (no new trades, existing positions untouched)",
    example: '"Stop the bot", "Pause trading"',
    category: "management",
    examplesByDestination: {
      sagemaster_forex: [
        { label: "Stop the bot", text: "Stop the bot" },
        { label: "Pause trading", text: "Pause trading" },
      ],
      sagemaster_crypto: [
        { label: "Stop the bot", text: "Stop the bot" },
        { label: "Pause trading", text: "Pause trading" },
      ],
    },
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

/** Return all action keys (for initializing enabled_actions). */
export function getAllActionKeys(destinationType: string): string[] {
  return getActionsForDestination(destinationType).map((a) => a.key);
}

export function getRequiredActionKeys(destinationType: string): string[] {
  return getActionsForDestination(destinationType)
    .filter((action) => action.required || action.isEntry)
    .map((action) => action.key);
}

export function getNormalizedEnabledActions(
  enabledActions: string[] | null | undefined,
  destinationType: string,
): string[] {
  const available = getAllActionKeys(destinationType);
  if (enabledActions == null) {
    return available;
  }

  const normalized = new Set(enabledActions);
  for (const key of getRequiredActionKeys(destinationType)) {
    normalized.add(key);
  }

  return available.filter((key) => normalized.has(key));
}

export function getActionExamples(
  action: ActionDefinition,
  destinationType: DestinationType,
): ActionExample[] {
  return action.examplesByDestination?.[destinationType]
    ?? [{ label: action.label, text: action.example.replace(/^"|"$/g, "") }];
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
    reason: "SageMaster doesn't support this via webhook",
  },
  {
    label: "Set SL to absolute price (crypto)",
    reason: "SageMaster crypto only supports relative SL offsets",
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
  const enabled = getNormalizedEnabledActions(enabledActions, destinationType).length;
  return `${enabled}/${total}`;
}
