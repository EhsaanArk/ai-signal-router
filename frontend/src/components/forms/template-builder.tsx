import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, X, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

// Known SGM fields with their dynamic placeholder values
const KNOWN_FIELDS: {
  key: string;
  label: string;
  placeholder: string;
  dynamic?: string;       // placeholder value when dynamic (e.g., "{{ticker}}")
  dynamicLabel?: string;  // label shown when dynamic
}[] = [
  { key: "type", label: "Action Type", placeholder: "e.g., start_deal", dynamic: "", dynamicLabel: "From signal direction" },
  { key: "assistId", label: "Assist ID", placeholder: "your-assist-id-here" },
  { key: "aiAssistId", label: "AI Assist ID", placeholder: "your-ai-assist-id-here" },
  { key: "tradeSymbol", label: "Trade Symbol", placeholder: "e.g., BTC/USDT", dynamic: "{{ticker}}", dynamicLabel: "From signal" },
  { key: "eventSymbol", label: "Event Symbol", placeholder: "e.g., BTC/USDT", dynamic: "{{ticker}}", dynamicLabel: "From signal" },
  { key: "symbol", label: "Symbol", placeholder: "e.g., EURUSD", dynamic: "{{ticker}}", dynamicLabel: "From signal" },
  { key: "source", label: "Source", placeholder: "e.g., forex, crypto", dynamic: "", dynamicLabel: "From signal asset class" },
  { key: "price", label: "Price", placeholder: "e.g., 1.1000", dynamic: "{{close}}", dynamicLabel: "From signal" },
  { key: "date", label: "Date", placeholder: "auto-filled", dynamic: "{{time}}", dynamicLabel: "Auto timestamp" },
  { key: "exchange", label: "Exchange", placeholder: "e.g., pptbitget" },
  // V2 entry fields
  { key: "balance", label: "Balance", placeholder: "e.g., 1000" },
  { key: "lots", label: "Lots", placeholder: "e.g., 1" },
  { key: "takeProfits", label: "Take Profits", placeholder: "e.g., [1.1050, 1.1100]", dynamic: "", dynamicLabel: "From signal" },
  { key: "takeProfitsPips", label: "TP Pips", placeholder: "e.g., [30, 60]", dynamic: "", dynamicLabel: "From signal" },
  { key: "stopLoss", label: "Stop Loss", placeholder: "e.g., 1.0950", dynamic: "", dynamicLabel: "From signal" },
  { key: "stopLossPips", label: "SL Pips", placeholder: "e.g., 30", dynamic: "", dynamicLabel: "From signal" },
  // Management action fields
  { key: "lotSize", label: "Lot Size", placeholder: "e.g., 0.1" },
  { key: "percentage", label: "Percentage", placeholder: "e.g., 50" },
  { key: "slAdjustment", label: "SL Adjustment", placeholder: "e.g., 0" },
  // Crypto-specific fields
  { key: "position_type", label: "Position Type", placeholder: "e.g., long", dynamic: "", dynamicLabel: "From signal" },
  { key: "is_market", label: "Is Market", placeholder: "true or false" },
  { key: "order_price", label: "Order Price", placeholder: "e.g., 30000" },
  { key: "take_profits", label: "Take Profits (%)", placeholder: "e.g., [1, 2, 5]", dynamic: "", dynamicLabel: "From signal" },
  { key: "sl_adjustment", label: "SL Adjustment (Crypto)", placeholder: "e.g., 0" },
];

const KNOWN_KEYS = new Set(KNOWN_FIELDS.map((f) => f.key));

/**
 * Sanitize TradingView placeholder variables in raw JSON text.
 *
 * SageMaster V2 templates contain bare {{...}} placeholders (e.g.,
 * `"takeProfits": [ {{tpPrice}} ]`, `"stopLoss": {{slPrice}}`) that are
 * NOT valid JSON.  This function replaces them with safe defaults so
 * `JSON.parse()` succeeds.
 */
export function sanitizeTradingViewJson(raw: string): string {
  return raw
    // Replace array placeholders: [ {{tpPrice}} ] → []
    .replace(/\[\s*\{\{[^}]+\}\}\s*\]/g, "[]")
    // Replace bare number/value placeholders: {{slPrice}} → null
    .replace(/:\s*\{\{[^}]+\}\}/g, ": null")
    // Strip trailing commas before } or ]
    .replace(/,\s*([}\]])/g, "$1");
}

interface FieldState {
  key: string;
  value: string;
  isDynamic: boolean;
  isCustom: boolean;
  disabled?: boolean;
}

interface TemplateBuilderProps {
  value: string;
  onChange: (text: string) => void;
  error?: string;
}

function isDynamicValue(value: string): boolean {
  return value === "" || value.startsWith("{{");
}

/** Check if a non-string value is "empty" (null, [], 0) — indicating it
 *  was likely a TradingView placeholder that the sanitizer replaced. */
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
        // Non-string values: check if this known field supports dynamic and
        // the value is an empty default (sanitizer replaced a placeholder)
        const supportsDynamic = knownField?.dynamic !== undefined;
        const shouldBeAuto = supportsDynamic && isEmptyDefault(val);
        fields.push({
          key,
          value: JSON.stringify(val),
          isDynamic: shouldBeAuto,
          isCustom: !KNOWN_KEYS.has(key),
        });
      } else {
        // Symbol fields default to dynamic — users rarely want a hardcoded symbol
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

/** For dynamic (Auto) fields, determine the correct empty placeholder value.
 *  String fields use their `dynamic` value (e.g., "{{close}}"), but non-string
 *  fields need their structural default ([] for arrays, null for numbers). */
function dynamicPlaceholder(known: typeof KNOWN_FIELDS[number] | undefined, currentValue: string): unknown {
  if (!known) return "";
  // If the field has a real placeholder like "{{close}}" or "{{ticker}}", use it
  if (known.dynamic && known.dynamic !== "") return known.dynamic;
  // For empty-string dynamic fields, infer the right empty default from the current value
  try {
    const parsed = JSON.parse(currentValue);
    if (Array.isArray(parsed)) return [];
    if (typeof parsed === "number") return null;
    if (parsed === null) return null;
  } catch { /* not JSON — fall through */ }
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
        // Known field, static: try to parse as JSON to preserve types (arrays, numbers)
        try {
          obj[field.key] = JSON.parse(field.value);
        } catch {
          obj[field.key] = field.value;
        }
      }
    } else {
      // Custom fields: try to parse as JSON, fallback to string
      try {
        obj[field.key] = JSON.parse(field.value);
      } catch {
        obj[field.key] = field.value;
      }
    }
  }
  return JSON.stringify(obj, null, 2);
}

export function TemplateBuilder({ value, onChange, error }: TemplateBuilderProps) {
  const [mode, setMode] = useState<"builder" | "json">("json");
  const [fields, setFields] = useState<FieldState[]>(() => {
    if (!value.trim()) return [];
    return parseJsonToFields(value) ?? [];
  });

  // Sync JSON → fields when switching to builder mode
  const switchToBuilder = useCallback(() => {
    if (value.trim()) {
      const parsed = parseJsonToFields(value);
      if (parsed) setFields(parsed);
    }
    setMode("builder");
  }, [value]);

  // Sync fields → JSON when switching to JSON mode or fields change
  const switchToJson = useCallback(() => {
    if (fields.length > 0) {
      onChange(fieldsToJson(fields));
    }
    setMode("json");
  }, [fields, onChange]);

  // Update JSON when fields change (in builder mode only)
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

  function removeField(index: number) {
    setFields((prev) => prev.filter((_, i) => i !== index));
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

  // Available known fields that aren't already added (disabled fields count as added)
  const availableFields = useMemo(() => {
    const usedKeys = new Set(fields.map((f) => f.key));
    return KNOWN_FIELDS.filter((f) => !usedKeys.has(f.key));
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

      {mode === "builder" ? (
        <div className="space-y-2">
          {fields.length === 0 && (
            <div className="rounded-md border border-dashed p-4 text-center">
              <p className="text-xs text-muted-foreground mb-2">
                No template fields configured. Add fields from the list below, or switch to JSON mode to paste a template.
              </p>
            </div>
          )}

          {fields.map((field, i) => {
            const known = KNOWN_FIELDS.find((f) => f.key === field.key);
            const hasDynamic = known?.dynamic !== undefined;
            const isDisabled = field.disabled;

            return (
              <div key={i} className={cn(
                "flex items-center gap-2 transition-opacity",
                isDisabled && "opacity-40",
              )}>
                {/* Field key */}
                {field.isCustom ? (
                  <Input
                    value={field.key}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      updateField(i, { key: e.target.value })
                    }
                    placeholder="field name"
                    disabled={isDisabled}
                    className="h-7 w-28 text-[11px] font-mono shrink-0"
                  />
                ) : (
                  <span className={cn(
                    "w-28 text-[11px] font-mono shrink-0 truncate",
                    isDisabled ? "text-muted-foreground/50 line-through" : "text-muted-foreground",
                  )} title={field.key}>
                    {field.key}
                  </span>
                )}

                {/* Value input */}
                <Input
                  value={field.isDynamic ? "" : field.value}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    updateField(i, { value: e.target.value, isDynamic: false })
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
                    onClick={() => updateField(i, { isDynamic: !field.isDynamic, value: field.isDynamic ? "" : field.value })}
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

                {/* Disable/enable toggle */}
                <button
                  type="button"
                  onClick={() => updateField(i, { disabled: !isDisabled })}
                  className={cn(
                    "h-7 w-7 flex items-center justify-center rounded-md shrink-0 transition-colors",
                    isDisabled
                      ? "text-muted-foreground/50 hover:text-foreground hover:bg-muted"
                      : "text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                  )}
                  title={isDisabled ? "Enable field" : "Disable field"}
                >
                  {isDisabled ? <Plus className="h-3 w-3" /> : <X className="h-3 w-3" />}
                </button>
              </div>
            );
          })}

          {/* Add field buttons */}
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
