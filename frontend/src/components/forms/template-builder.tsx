import { useCallback, useEffect, useMemo, useState } from "react";
import { Eye, EyeOff, Info, Lock, Plus, Zap } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Field metadata — single source of truth for SageMaster webhook fields
// ---------------------------------------------------------------------------

type Platform = "forex" | "crypto";
type FieldGroup = "core" | "entry" | "risk" | "management";

interface KnownField {
  key: string;
  label: string;
  placeholder: string;
  dynamic?: string;
  dynamicLabel?: string;
  /** Which platforms this field belongs to. Omit = all platforms. */
  platforms?: Platform[];
  /** Which platform requires this field. "all" = always required. */
  required?: Platform | "all";
  /** Only relevant for V2 payload version (Forex). */
  v2Only?: boolean;
  /** Required for V2 entries — needs at least one from each group (TP + SL). */
  v2Required?: "tp" | "sl";
  /** Visual grouping in builder. */
  group: FieldGroup;
  /** Help text shown in tooltip. */
  description: string;
}

const KNOWN_FIELDS: KnownField[] = [
  // --- Core fields (always required) ---
  { key: "type", label: "Action Type", placeholder: "e.g., start_deal", dynamic: "", dynamicLabel: "From signal direction", required: "all", group: "core", description: "The trade action. Auto-filled based on the signal direction (long/short/close)." },
  { key: "assistId", label: "Assist ID", placeholder: "your-assist-id-here", platforms: ["forex"], required: "forex", group: "core", description: "Your SageMaster Forex strategy ID. Find it in Assists > Overview on sfx.sagemaster.io." },
  { key: "aiAssistId", label: "AI Assist ID", placeholder: "your-ai-assist-id-here", platforms: ["crypto"], required: "crypto", group: "core", description: "Your SageMaster Crypto assist ID. Find it in Assists > Overview on app.sagemaster.io." },
  { key: "source", label: "Source", placeholder: "e.g., forex", dynamic: "", dynamicLabel: "From signal asset class", platforms: ["forex"], required: "forex", group: "core", description: "Asset class identifier. Auto-filled as 'forex' for Forex destinations." },
  { key: "symbol", label: "Symbol", placeholder: "e.g., EURUSD", dynamic: "{{ticker}}", dynamicLabel: "From signal", platforms: ["forex"], required: "forex", group: "core", description: "Trading pair symbol. Auto-filled from the signal (e.g., XAUUSD, EURUSD)." },
  { key: "date", label: "Date", placeholder: "auto-filled", dynamic: "{{time}}", dynamicLabel: "Auto timestamp", required: "all", group: "core", description: "Timestamp of the signal. Auto-filled with the current UTC time." },
  { key: "exchange", label: "Exchange", placeholder: "e.g., pptbitget", platforms: ["crypto"], required: "crypto", group: "core", description: "Crypto exchange name (e.g., binance, pptbitget). Must match your SageMaster exchange config." },
  { key: "tradeSymbol", label: "Trade Symbol", placeholder: "e.g., BTC/USDT", dynamic: "{{ticker}}", dynamicLabel: "From signal", platforms: ["crypto"], required: "crypto", group: "core", description: "Crypto trading pair. Auto-filled from the signal." },
  { key: "eventSymbol", label: "Event Symbol", placeholder: "e.g., BTC/USDT", dynamic: "{{ticker}}", dynamicLabel: "From signal", platforms: ["crypto"], required: "crypto", group: "core", description: "Event trigger symbol for SageMaster Crypto. Usually same as tradeSymbol." },

  // --- Entry fields ---
  { key: "price", label: "Price", placeholder: "e.g., 1.1000", dynamic: "{{close}}", dynamicLabel: "From signal", group: "entry", description: "Entry price. Auto-filled from the signal's price data." },
  { key: "balance", label: "Balance", placeholder: "e.g., 1000", platforms: ["forex"], v2Only: true, group: "entry", description: "Account balance for position sizing. Used by SageMaster's money management." },
  { key: "lots", label: "Lots", placeholder: "e.g., 1", platforms: ["forex"], v2Only: true, group: "entry", description: "Position size in lots. Overrides the strategy's default lot size." },

  // --- Risk management fields ---
  { key: "takeProfits", label: "Take Profits", placeholder: "e.g., [1.1050, 1.1100]", dynamic: "", dynamicLabel: "From signal", platforms: ["forex"], v2Only: true, v2Required: "tp", group: "risk", description: "Array of TP price levels. Required for V2 — use this OR TP Pips (at least one)." },
  { key: "takeProfitsPips", label: "TP Pips", placeholder: "e.g., [30, 60]", dynamic: "", dynamicLabel: "From signal", platforms: ["forex"], v2Only: true, v2Required: "tp", group: "risk", description: "Take profit as pip distances. Required for V2 — use this OR Take Profits (at least one)." },
  { key: "stopLoss", label: "Stop Loss", placeholder: "e.g., 1.0950", dynamic: "", dynamicLabel: "From signal", platforms: ["forex"], v2Only: true, v2Required: "sl", group: "risk", description: "Stop loss price level. Required for V2 — use this OR SL Pips (at least one)." },
  { key: "stopLossPips", label: "SL Pips", placeholder: "e.g., 30", dynamic: "", dynamicLabel: "From signal", platforms: ["forex"], v2Only: true, v2Required: "sl", group: "risk", description: "Stop loss as pip distance. Required for V2 — use this OR Stop Loss (at least one)." },
  { key: "take_profits", label: "Take Profits (%)", placeholder: "e.g., [1, 2, 5]", dynamic: "", dynamicLabel: "From signal", platforms: ["crypto"], group: "risk", description: "Crypto TP values as percentages (e.g., [1, 2, 5] = 1%, 2%, 5% from entry)." },

  // --- Trade management fields ---
  { key: "lotSize", label: "Lot Size", placeholder: "e.g., 0.1", platforms: ["forex"], group: "management", description: "Lot size for partial close operations." },
  { key: "percentage", label: "Percentage", placeholder: "e.g., 50", group: "management", description: "Percentage for partial close operations (e.g., close 50% of position)." },
  { key: "slAdjustment", label: "SL Adjustment", placeholder: "e.g., 0", platforms: ["forex"], group: "management", description: "Stop loss adjustment for breakeven moves. 0 = move SL to entry price." },
  { key: "position_type", label: "Position Type", placeholder: "e.g., long", dynamic: "", dynamicLabel: "From signal", platforms: ["crypto"], group: "management", description: "Required for crypto management actions (close, partial close, breakeven)." },
  { key: "is_market", label: "Is Market", placeholder: "true or false", platforms: ["crypto"], group: "management", description: "Whether to execute as market order (true) or limit order (false)." },
  { key: "order_price", label: "Order Price", placeholder: "e.g., 30000", platforms: ["crypto"], group: "management", description: "Limit order price for crypto extra orders." },
  { key: "sl_adjustment", label: "SL Adjustment (Crypto)", placeholder: "e.g., 0", platforms: ["crypto"], group: "management", description: "Crypto stop loss adjustment. 0 = move to breakeven." },
];

const KNOWN_KEYS = new Set(KNOWN_FIELDS.map((f) => f.key));

const GROUP_LABELS: Record<FieldGroup, string> = {
  core: "Core Fields",
  entry: "Entry Fields",
  risk: "Risk Management",
  management: "Trade Management",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Sanitize TradingView placeholder variables in raw JSON text.
 */
export function sanitizeTradingViewJson(raw: string): string {
  return raw
    .replace(/\[\s*\{\{[^}]+\}\}\s*\]/g, "[]")
    .replace(/:\s*\{\{[^}]+\}\}/g, ": null")
    .replace(/,\s*([}\]])/g, "$1");
}

/** Resolve whether a known field is required given the current context. */
function isFieldRequired(
  field: KnownField,
  destinationType?: string,
  payloadVersion?: string,
  moneyManagementMode?: MoneyManagementMode,
): boolean {
  // V2-conditional fields (TP/SL) — required when V2 + forex
  if (field.v2Required) {
    return payloadVersion === "V2" && destinationType === "sagemaster_forex";
  }
  // MM mode makes balance/lots required for specific modes
  if (payloadVersion === "V2" && destinationType === "sagemaster_forex" && moneyManagementMode) {
    if (field.key === "balance" && moneyManagementMode === "with_ratio") return true;
    if (field.key === "lots" && (moneyManagementMode === "with_ratio" || moneyManagementMode === "without_ratio")) return true;
  }
  if (!field.required) return false;
  if (field.required === "all") return true;
  // V2-only fields are only required when V2 is selected
  if (field.v2Only && payloadVersion !== "V2") return false;
  const platform = destinationType === "sagemaster_crypto" ? "crypto" : "forex";
  return field.required === platform;
}

/** Money management mode — controls balance/lots visibility in V2 Forex. */
export type MoneyManagementMode = "default" | "with_ratio" | "without_ratio" | "unsure";

const MM_MODE_OPTIONS: { value: MoneyManagementMode; label: string }[] = [
  { value: "unsure", label: "I'm not sure (show all fields)" },
  { value: "default", label: "Default (fixed lot from strategy)" },
  { value: "with_ratio", label: "Indicator % with ratio check (needs balance + lots)" },
  { value: "without_ratio", label: "Indicator % without ratio check (needs lots)" },
];

export function MoneyManagementSelect({ value, onChange }: { value: MoneyManagementMode; onChange: (v: MoneyManagementMode) => void }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs">Money Management Mode</Label>
      <Select value={value} onValueChange={(v) => onChange(v as MoneyManagementMode)}>
        <SelectTrigger className="h-8 text-sm">
          <SelectValue placeholder="Select your Assist's money management..." />
        </SelectTrigger>
        <SelectContent>
          {MM_MODE_OPTIONS.map((opt) => (
            <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>
      <p className="text-[10px] text-muted-foreground">
        Found in your SageMaster Assist settings. Controls which fields are shown in the template builder.
      </p>
    </div>
  );
}

/** Check if a field is relevant for the current destination + version + MM mode. */
function isFieldVisible(
  field: KnownField,
  destinationType?: string,
  payloadVersion?: string,
  moneyManagementMode?: MoneyManagementMode,
): boolean {
  // Custom destinations: show everything
  if (!destinationType || destinationType === "custom") return true;
  const platform: Platform = destinationType === "sagemaster_crypto" ? "crypto" : "forex";
  // Filter by platform
  if (field.platforms && !field.platforms.includes(platform)) return false;
  // Filter V2-only fields for V1
  if (field.v2Only && payloadVersion === "V1") return false;
  // MM mode filtering for balance/lots (V2 Forex only)
  if (moneyManagementMode && moneyManagementMode !== "unsure" && payloadVersion === "V2" && destinationType === "sagemaster_forex") {
    if (field.key === "balance" && (moneyManagementMode === "default" || moneyManagementMode === "without_ratio")) return false;
    if (field.key === "lots" && moneyManagementMode === "default") return false;
  }
  return true;
}

/**
 * Validate that all required fields are present and enabled in a template.
 * Returns array of missing field labels (empty = valid).
 */
export function validateRequiredFields(
  json: string,
  destinationType: string,
  payloadVersion: string,
  moneyManagementMode?: MoneyManagementMode,
): string[] {
  if (!json.trim()) return [];
  let obj: Record<string, unknown>;
  try {
    obj = JSON.parse(sanitizeTradingViewJson(json));
  } catch {
    return []; // JSON parse errors handled elsewhere
  }

  const missing: string[] = [];
  for (const field of KNOWN_FIELDS) {
    if (!isFieldRequired(field, destinationType, payloadVersion, moneyManagementMode)) continue;
    if (!isFieldVisible(field, destinationType, payloadVersion, moneyManagementMode)) continue;
    if (!(field.key in obj)) {
      missing.push(field.label);
    }
  }

  // V2 Forex: need at least one TP method and one SL method
  if (destinationType === "sagemaster_forex" && payloadVersion === "V2") {
    const hasTP = "takeProfits" in obj || "takeProfitsPips" in obj;
    const hasSL = "stopLoss" in obj || "stopLossPips" in obj;
    if (!hasTP && !missing.includes("Take Profits") && !missing.includes("TP Pips")) {
      missing.push("Take Profits or TP Pips");
    }
    if (!hasSL && !missing.includes("Stop Loss") && !missing.includes("SL Pips")) {
      missing.push("Stop Loss or SL Pips");
    }
  }

  return missing;
}

// ---------------------------------------------------------------------------
// Field state & JSON conversion
// ---------------------------------------------------------------------------

interface FieldState {
  key: string;
  value: string;
  isDynamic: boolean;
  isCustom: boolean;
  disabled?: boolean;
}

function isDynamicValue(value: string): boolean {
  return value === "" || value.startsWith("{{");
}

function isEmptyDefault(val: unknown): boolean {
  if (val === null || val === undefined) return true;
  if (Array.isArray(val) && val.length === 0) return true;
  return false;
}

function parseJsonToFields(json: string): FieldState[] | null {
  try {
    const obj = JSON.parse(sanitizeTradingViewJson(json));
    if (typeof obj !== "object" || Array.isArray(obj)) return null;
    const fields: FieldState[] = [];
    for (const [key, val] of Object.entries(obj)) {
      const knownField = KNOWN_FIELDS.find((f) => f.key === key);
      if (typeof val !== "string") {
        const supportsDynamic = knownField?.dynamic !== undefined;
        const shouldBeAuto = supportsDynamic && isEmptyDefault(val);
        fields.push({
          key,
          value: JSON.stringify(val),
          isDynamic: shouldBeAuto,
          isCustom: !KNOWN_KEYS.has(key),
        });
      } else {
        const isSymbolField = knownField?.dynamic === "{{ticker}}";
        const dynamic = knownField?.dynamic !== undefined && (isDynamicValue(val) || isSymbolField);
        fields.push({ key, value: val, isDynamic: dynamic, isCustom: !KNOWN_KEYS.has(key) });
      }
    }
    return fields;
  } catch {
    return null;
  }
}

function dynamicPlaceholder(known: KnownField | undefined, currentValue: string): unknown {
  if (!known) return "";
  if (known.dynamic && known.dynamic !== "") return known.dynamic;
  try {
    const parsed = JSON.parse(currentValue);
    if (Array.isArray(parsed)) return [];
    if (typeof parsed === "number") return null;
    if (parsed === null) return null;
  } catch { /* not JSON */ }
  return "";
}

function fieldsToJson(fields: FieldState[]): string {
  const obj: Record<string, unknown> = {};
  for (const field of fields) {
    if (!field.key || field.disabled) continue;
    if (!field.isCustom) {
      if (field.isDynamic) {
        const known = KNOWN_FIELDS.find((f) => f.key === field.key);
        obj[field.key] = dynamicPlaceholder(known, field.value);
      } else {
        try {
          obj[field.key] = JSON.parse(field.value);
        } catch {
          obj[field.key] = field.value;
        }
      }
    } else {
      try {
        obj[field.key] = JSON.parse(field.value);
      } catch {
        obj[field.key] = field.value;
      }
    }
  }
  return JSON.stringify(obj, null, 2);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface TemplateBuilderProps {
  value: string;
  onChange: (text: string) => void;
  error?: string;
  destinationType?: string;
  payloadVersion?: string;
  moneyManagementMode?: MoneyManagementMode;
}

export function TemplateBuilder({ value, onChange, error, destinationType, payloadVersion, moneyManagementMode }: TemplateBuilderProps) {
  const [mode, setMode] = useState<"builder" | "json">("json");
  const [fields, setFields] = useState<FieldState[]>(() => {
    if (!value.trim()) return [];
    return parseJsonToFields(value) ?? [];
  });

  const switchToBuilder = useCallback(() => {
    if (value.trim()) {
      const parsed = parseJsonToFields(value);
      if (parsed) setFields(parsed);
    }
    setMode("builder");
  }, [value]);

  const switchToJson = useCallback(() => {
    if (fields.length > 0) {
      onChange(fieldsToJson(fields));
    }
    setMode("json");
  }, [fields, onChange]);

  useEffect(() => {
    if (mode !== "builder") return;
    if (fields.length === 0 && !value.trim()) return;
    if (fields.length === 0) {
      onChange("");
      return;
    }
    const newJson = fieldsToJson(fields);
    if (newJson !== value) {
      onChange(newJson);
    }
  }, [fields, mode]); // eslint-disable-line react-hooks/exhaustive-deps

  function updateField(index: number, updates: Partial<FieldState>) {
    setFields((prev) =>
      prev.map((f, i) => (i === index ? { ...f, ...updates } : f))
    );
  }

  function addKnownField(key: string) {
    const known = KNOWN_FIELDS.find((f) => f.key === key);
    if (!known) return;
    setFields((prev) => [...prev, {
      key,
      value: "",
      isDynamic: known.dynamic !== undefined,
      isCustom: false,
    }]);
  }

  function addCustomField() {
    setFields((prev) => [...prev, {
      key: "",
      value: "",
      isDynamic: false,
      isCustom: true,
    }]);
  }

  // Filter available fields by platform + version + MM mode
  const availableFields = useMemo(() => {
    const usedKeys = new Set(fields.map((f) => f.key));
    return KNOWN_FIELDS
      .filter((f) => !usedKeys.has(f.key))
      .filter((f) => isFieldVisible(f, destinationType, payloadVersion, moneyManagementMode));
  }, [fields, destinationType, payloadVersion, moneyManagementMode]);

  // Group fields for visual sections
  const groupedFields = useMemo(() => {
    const groups: { group: FieldGroup; label: string; fields: { field: FieldState; index: number; known: KnownField | undefined }[] }[] = [];
    const groupMap = new Map<FieldGroup, typeof groups[number]>();

    fields.forEach((field, index) => {
      const known = KNOWN_FIELDS.find((f) => f.key === field.key);
      const group = known?.group ?? "management";
      if (!groupMap.has(group)) {
        const entry = { group, label: GROUP_LABELS[group], fields: [] as typeof groups[number]["fields"] };
        groupMap.set(group, entry);
        groups.push(entry);
      }
      groupMap.get(group)!.fields.push({ field, index, known });
    });

    return groups;
  }, [fields]);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="text-xs">Webhook Body Template</Label>
        <div className="flex rounded-sm border text-[10px]">
          <button
            type="button"
            onClick={mode === "json" ? switchToBuilder : undefined}
            className={cn(
              "px-2.5 py-1 transition-colors",
              mode === "builder"
                ? "bg-primary/10 text-primary font-medium"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Builder
          </button>
          <button
            type="button"
            onClick={mode === "builder" ? switchToJson : undefined}
            className={cn(
              "px-2.5 py-1 transition-colors border-l",
              mode === "json"
                ? "bg-primary/10 text-primary font-medium"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            JSON
          </button>
        </div>
      </div>

      <p className="text-[11px] text-muted-foreground">
        Optional. Configure the webhook payload sent to SageMaster. Use the builder for guided setup or paste raw JSON.
      </p>

      {payloadVersion === "V2" && destinationType === "sagemaster_forex" && (
        <div className="rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-2">
          <p className="text-[11px] text-amber-600 dark:text-amber-400">
            <span className="font-medium">V2 requires TP and SL in every entry signal.</span>{" "}
            If your signal provider doesn't always include TP/SL, either switch to V1
            (uses your strategy's fixed TP/SL) or set static fallback values below.
          </p>
        </div>
      )}

      {mode === "builder" ? (
        <div className="space-y-3">
          {fields.length === 0 && (
            <div className="rounded-md border border-dashed p-4 text-center">
              <p className="text-xs text-muted-foreground mb-2">
                No template fields configured. Add fields from the list below, or switch to JSON mode to paste a template.
              </p>
            </div>
          )}

          {groupedFields.map((group) => (
            <div key={group.group}>
              {/* Group label */}
              <p className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground/50 mb-1.5">
                {group.label}
              </p>

              <div className="space-y-1.5">
                {group.fields.map(({ field, index, known }) => {
                  const hasDynamic = known?.dynamic !== undefined;
                  const isDisabled = field.disabled;
                  const required = known ? isFieldRequired(known, destinationType, payloadVersion, moneyManagementMode) : false;

                  return (
                    <div key={index} className={cn(
                      "flex items-center gap-2 transition-opacity",
                      isDisabled && "opacity-40",
                    )}>
                      {/* Field key + info tooltip */}
                      <div className="w-28 shrink-0 flex items-center gap-1">
                        {field.isCustom ? (
                          <Input
                            value={field.key}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                              updateField(index, { key: e.target.value })
                            }
                            placeholder="field name"
                            disabled={isDisabled}
                            className="h-7 text-[11px] font-mono"
                          />
                        ) : (
                          <>
                            <span className={cn(
                              "text-[11px] font-mono truncate",
                              isDisabled ? "text-muted-foreground/50 line-through" : "text-muted-foreground",
                            )} title={field.key}>
                              {field.key}
                            </span>
                            {known?.description && (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Info className="h-2.5 w-2.5 text-muted-foreground/40 shrink-0 cursor-help" />
                                </TooltipTrigger>
                                <TooltipContent side="top" className="max-w-[250px]">
                                  <p className="text-xs">{known.description}</p>
                                </TooltipContent>
                              </Tooltip>
                            )}
                          </>
                        )}
                      </div>

                      {/* Value input */}
                      <Input
                        value={field.isDynamic ? "" : field.value}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          updateField(index, { value: e.target.value, isDynamic: false })
                        }
                        placeholder={
                          field.isDynamic
                            ? (known?.dynamicLabel || "Dynamic")
                            : (known?.placeholder || "value")
                        }
                        disabled={field.isDynamic || isDisabled}
                        className={cn(
                          "h-7 flex-1 text-[11px] font-mono",
                          field.isDynamic && !isDisabled && "bg-primary/5 text-muted-foreground"
                        )}
                      />

                      {/* Dynamic toggle */}
                      {hasDynamic && !isDisabled && (
                        <button
                          type="button"
                          onClick={() => updateField(index, { isDynamic: !field.isDynamic, value: field.isDynamic ? "" : field.value })}
                          className={cn(
                            "flex items-center gap-1 rounded-sm px-2 py-1 text-[10px] font-medium transition-colors shrink-0",
                            field.isDynamic
                              ? "bg-primary/10 text-primary"
                              : "text-muted-foreground hover:text-foreground hover:bg-muted"
                          )}
                          title={field.isDynamic ? "Using signal data" : "Click to use signal data"}
                        >
                          <Zap className="h-2.5 w-2.5" />
                          {field.isDynamic ? "Auto" : "Static"}
                        </button>
                      )}

                      {/* Required badge OR disable toggle */}
                      {required ? (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="flex items-center gap-0.5 text-[9px] font-medium text-amber-500/80 shrink-0 px-1.5">
                              <Lock className="h-2.5 w-2.5" />
                              {known?.v2Required ? "V2 Req" : "Required"}
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p className="text-xs">
                              {known?.v2Required
                                ? `Required for V2 — need at least one ${known.v2Required === "tp" ? "Take Profit" : "Stop Loss"} method`
                                : "Required by SageMaster — cannot be disabled"}
                            </p>
                          </TooltipContent>
                        </Tooltip>
                      ) : (
                        <button
                          type="button"
                          onClick={() => updateField(index, { disabled: !isDisabled })}
                          className={cn(
                            "h-7 w-7 flex items-center justify-center rounded-md shrink-0 transition-colors",
                            isDisabled
                              ? "text-muted-foreground/50 hover:text-foreground hover:bg-muted"
                              : "text-muted-foreground hover:text-muted-foreground/60 hover:bg-muted"
                          )}
                          title={isDisabled ? "Enable field — include in webhook" : "Disable field — exclude from webhook"}
                        >
                          {isDisabled ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          {/* Add field buttons — filtered by platform + version */}
          <div className="flex flex-wrap gap-1 pt-1">
            {availableFields.slice(0, 6).map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => addKnownField(f.key)}
                className="rounded-sm border border-dashed px-2 py-0.5 text-[10px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
              >
                + {f.key}
              </button>
            ))}
            {availableFields.length > 6 && (
              <span className="text-[10px] text-muted-foreground px-1 py-0.5">
                +{availableFields.length - 6} more
              </span>
            )}
            <button
              type="button"
              onClick={addCustomField}
              className="rounded-sm border border-dashed px-2 py-0.5 text-[10px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
            >
              <Plus className="h-2.5 w-2.5 inline mr-0.5" />
              Custom
            </button>
          </div>
        </div>
      ) : (
        <Textarea
          value={value}
          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => onChange(e.target.value)}
          placeholder={`{\n  "type": "start_deal",\n  "tradeSymbol": "{{ticker}}",\n  "price": "{{close}}"\n}`}
          rows={8}
          className="font-mono text-[11px]"
        />
      )}

      {error && <p className="text-[11px] text-destructive">{error}</p>}
    </div>
  );
}
