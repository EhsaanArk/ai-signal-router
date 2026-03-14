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
];

const KNOWN_KEYS = new Set(KNOWN_FIELDS.map((f) => f.key));

interface FieldState {
  key: string;
  value: string;
  isDynamic: boolean;
  isCustom: boolean;
}

interface TemplateBuilderProps {
  value: string;
  onChange: (text: string) => void;
  error?: string;
}

function isDynamicValue(value: string): boolean {
  return value === "" || value.startsWith("{{");
}

function parseJsonToFields(json: string): FieldState[] | null {
  try {
    const obj = JSON.parse(json);
    if (typeof obj !== "object" || Array.isArray(obj)) return null;
    const fields: FieldState[] = [];
    for (const [key, val] of Object.entries(obj)) {
      if (typeof val !== "string") {
        // Non-string values: store as JSON string, mark as custom
        fields.push({ key, value: JSON.stringify(val), isDynamic: false, isCustom: !KNOWN_KEYS.has(key) });
      } else {
        const knownField = KNOWN_FIELDS.find((f) => f.key === key);
        const dynamic = knownField?.dynamic !== undefined && isDynamicValue(val);
        fields.push({ key, value: val, isDynamic: dynamic, isCustom: !KNOWN_KEYS.has(key) });
      }
    }
    return fields;
  } catch {
    return null;
  }
}

function fieldsToJson(fields: FieldState[]): string {
  const obj: Record<string, unknown> = {};
  for (const field of fields) {
    if (!field.key) continue;
    // Try to parse non-string values back
    if (!field.isCustom) {
      if (field.isDynamic) {
        const known = KNOWN_FIELDS.find((f) => f.key === field.key);
        obj[field.key] = known?.dynamic ?? "";
      } else {
        obj[field.key] = field.value;
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

  // Available known fields that aren't already added
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

            return (
              <div key={i} className="flex items-center gap-2">
                {/* Field key */}
                {field.isCustom ? (
                  <Input
                    value={field.key}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      updateField(i, { key: e.target.value })
                    }
                    placeholder="field name"
                    className="h-7 w-28 text-[11px] font-mono shrink-0"
                  />
                ) : (
                  <span className="w-28 text-[11px] font-mono text-muted-foreground shrink-0 truncate" title={field.key}>
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
                  disabled={field.isDynamic}
                  className={cn(
                    "h-7 flex-1 text-[11px] font-mono",
                    field.isDynamic && "bg-primary/5 text-muted-foreground"
                  )}
                />

                {/* Dynamic toggle */}
                {hasDynamic && (
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

                {/* Remove */}
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0"
                  onClick={() => removeField(i)}
                >
                  <X className="h-3 w-3" />
                </Button>
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
