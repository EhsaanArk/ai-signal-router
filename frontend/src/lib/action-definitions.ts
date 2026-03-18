export interface ActionDefinition {
  key: string;
  label: string;
  description: string;
  example: string;
  isEntry?: boolean;
  forexOnly?: boolean;
}

export const ACTION_DEFINITIONS: ActionDefinition[] = [
  {
    key: "start_long_market_deal",
    label: "Entry Long",
    description: "Open a new long/buy position",
    example: '"Buy EURUSD at market"',
    isEntry: true,
  },
  {
    key: "start_short_market_deal",
    label: "Entry Short",
    description: "Open a new short/sell position",
    example: '"Sell GBPUSD at market"',
    isEntry: true,
  },
  {
    key: "start_long_limit_deal",
    label: "Entry Long (Limit)",
    description: "Open a new long/buy limit order",
    example: '"Buy limit EURUSD @ 1.0950"',
    isEntry: true,
  },
  {
    key: "start_short_limit_deal",
    label: "Entry Short (Limit)",
    description: "Open a new short/sell limit order",
    example: '"Sell limit GBPUSD @ 1.2500"',
    isEntry: true,
  },
  {
    key: "close_order_at_market_price",
    label: "Close Position",
    description: "Fully close an open trade",
    example: '"Close all", "Exit trade"',
  },
  {
    key: "partially_close_by_percentage",
    label: "Partial Close (%)",
    description: "Close a percentage of position",
    example: '"Close 50%", "Take half off"',
  },
  {
    key: "partially_close_by_lot",
    label: "Partial Close (Lots)",
    description: "Close a specific lot amount",
    example: '"Close 0.5 lots"',
    forexOnly: true,
  },
  {
    key: "move_sl_to_breakeven",
    label: "Breakeven",
    description: "Move stop loss to entry price",
    example: '"Move SL to BE", "Breakeven"',
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
  const isEntry = actionKey.startsWith("start_");
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
    } else if (actionKey === "move_sl_to_breakeven") {
      payload["slAdjustment"] = 0;
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
  return ACTION_DEFINITIONS.filter(
    (a) => !a.forexOnly || destinationType === "sagemaster_forex",
  );
}

/** Return all action keys (for initializing enabled_actions). */
export function getAllActionKeys(destinationType: string): string[] {
  return getActionsForDestination(destinationType).map((a) => a.key);
}
