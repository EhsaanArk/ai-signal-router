import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getNormalizedEnabledActions,
} from "@/lib/action-definitions";
import { RouteCommandsWorkspace } from "@/components/routes/route-commands-workspace";
import type { DestinationType } from "@/types/api";

interface Props {
  initialData?: {
    enabled_actions?: string[];
    risk_overrides?: Record<string, unknown>;
    keyword_blacklist?: string[];
  };
  wizardData: {
    webhook_body_template?: Record<string, unknown> | null;
    destination_type?: DestinationType;
    payload_version?: "V1" | "V2";
  };
  onNext: (enabledActions: string[], riskOverrides: Record<string, unknown>, keywordBlacklist: string[]) => void;
  onBack: (enabledActions: string[], riskOverrides: Record<string, unknown>, keywordBlacklist: string[]) => void;
  isFinalStep?: boolean;
  onFinish?: (enabledActions: string[], riskOverrides: Record<string, unknown>, keywordBlacklist: string[]) => void;
  isSubmitting?: boolean;
}

export function StepActions({ initialData, wizardData, onNext, onBack, isFinalStep, onFinish, isSubmitting }: Props) {
  const destinationType = wizardData.destination_type || "sagemaster_forex";

  const [enabledActions, setEnabledActions] = useState<Set<string>>(
    () => new Set(getNormalizedEnabledActions(initialData?.enabled_actions, destinationType)),
  );
  const [lotSize, setLotSize] = useState(
    () => (initialData?.risk_overrides?.lots as string) ?? "",
  );
  const [keywords, setKeywords] = useState<string[]>(
    () => initialData?.keyword_blacklist ?? [],
  );
  const [keywordInput, setKeywordInput] = useState("");

  function toggleAction(key: string) {
    setEnabledActions((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function addKeyword() {
    const kw = keywordInput.trim();
    if (kw && !keywords.includes(kw)) {
      setKeywords((prev) => [...prev, kw]);
    }
    setKeywordInput("");
  }

  function removeKeyword(kw: string) {
    setKeywords((prev) => prev.filter((k) => k !== kw));
  }

  function handleNext() {
    const riskOverrides: Record<string, unknown> = {};
    if (lotSize.trim()) {
      riskOverrides.lots = lotSize.trim();
    }
    const normalizedEnabled = getNormalizedEnabledActions(Array.from(enabledActions), destinationType);
    if (isFinalStep && onFinish) {
      onFinish(normalizedEnabled, riskOverrides, keywords);
    } else {
      onNext(normalizedEnabled, riskOverrides, keywords);
    }
  }

  return (
    <div className="space-y-4">
      <RouteCommandsWorkspace
        destinationType={destinationType}
        enabledActions={enabledActions}
        onToggleAction={toggleAction}
        mode="create"
      />

      {/* Lot Size Override (V2 only) */}
      {wizardData.payload_version === "V2" && (
        <div className="space-y-1.5">
          <Label htmlFor="lot-size-override" className="text-xs">
            Lot Size Override
          </Label>
          <Input
            id="lot-size-override"
            type="text"
            inputMode="decimal"
            placeholder="e.g., 0.1 (leave empty for signal default)"
            value={lotSize}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setLotSize(e.target.value)
            }
            className="h-8 text-sm"
          />
        </div>
      )}

      {/* Keyword Blacklist */}
      <div className="space-y-1.5">
        <Label className="text-xs">Keyword Blacklist</Label>
        <p className="text-[10px] text-muted-foreground">
          Messages containing any of these keywords will be ignored for this route.
        </p>
        <div className="flex gap-2">
          <Input
            type="text"
            placeholder="e.g., demo, paper trade"
            value={keywordInput}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setKeywordInput(e.target.value)}
            onKeyDown={(e: React.KeyboardEvent) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addKeyword();
              }
            }}
            className="h-8 text-sm flex-1"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8"
            onClick={addKeyword}
            disabled={!keywordInput.trim()}
          >
            Add
          </Button>
        </div>
        {keywords.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {keywords.map((kw) => (
              <span
                key={kw}
                className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-xs"
              >
                {kw}
                <button
                  type="button"
                  onClick={() => removeKeyword(kw)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  &times;
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="flex gap-2 pt-2">
        <Button variant="outline" size="sm" onClick={() => {
          const riskOverrides: Record<string, unknown> = {};
          if (lotSize.trim()) riskOverrides.lots = lotSize.trim();
          onBack(getNormalizedEnabledActions(Array.from(enabledActions), destinationType), riskOverrides, keywords);
        }}>
          Back
        </Button>
        <Button size="sm" onClick={handleNext} disabled={isSubmitting}>
          {isFinalStep ? (isSubmitting ? "Creating..." : "Create Rule") : "Next"}
        </Button>
      </div>
    </div>
  );
}
