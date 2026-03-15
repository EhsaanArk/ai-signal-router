import { useState } from "react";
import { ArrowRight, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Props {
  initialData?: { symbol_mappings?: Record<string, string> };
  onFinish: (mappings: Record<string, string>) => void;
  onBack: (mappings: Record<string, string>) => void;
  isSubmitting: boolean;
}

export function StepSymbolMappings({ initialData, onFinish, onBack, isSubmitting }: Props) {
  const [pairs, setPairs] = useState<{ from: string; to: string }[]>(() => {
    const mappings = initialData?.symbol_mappings;
    if (!mappings || Object.keys(mappings).length === 0) return [];
    return Object.entries(mappings).map(([from, to]) => ({ from, to }));
  });

  function addPair() {
    setPairs((prev) => [...prev, { from: "", to: "" }]);
  }

  function removePair(index: number) {
    setPairs((prev) => prev.filter((_, i) => i !== index));
  }

  function updatePair(index: number, field: "from" | "to", value: string) {
    setPairs((prev) =>
      prev.map((p, i) => (i === index ? { ...p, [field]: value } : p))
    );
  }

  function handleSubmit() {
    const mappings: Record<string, string> = {};
    for (const pair of pairs) {
      if (pair.from && pair.to) {
        mappings[pair.from] = pair.to;
      }
    }
    onFinish(mappings);
  }

  return (
    <div className="space-y-3">
      <div>
        <Label className="text-xs">Symbol Mappings</Label>
        <p className="text-[10px] text-muted-foreground mt-0.5">
          Optional. Map signal symbols to your broker's names (e.g., GOLD → XAUUSD).
        </p>
      </div>

      {pairs.length > 0 && (
        <div className="space-y-1.5">
          {pairs.map((pair, i) => (
            <div key={i} className="flex items-center gap-1.5 rounded-md bg-muted/30 px-2 py-1">
              <Input
                placeholder="GOLD"
                value={pair.from}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => updatePair(i, "from", e.target.value)}
                className="h-7 text-xs font-mono flex-1"
              />
              <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
              <Input
                placeholder="XAUUSD"
                value={pair.to}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => updatePair(i, "to", e.target.value)}
                className="h-7 text-xs font-mono flex-1"
              />
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0"
                onClick={() => removePair(i)}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          ))}
        </div>
      )}

      {pairs.length === 0 && (
        <div className="rounded-md border border-dashed p-4 text-center">
          <p className="text-[11px] text-muted-foreground">
            No mappings configured. Most users don't need this.
          </p>
        </div>
      )}

      <Button variant="outline" size="sm" className="h-7 text-xs" onClick={addPair}>
        <Plus className="mr-1 h-3 w-3" />
        Add Mapping
      </Button>

      <div className="flex gap-2 pt-2">
        <Button variant="outline" size="sm" onClick={() => {
          const mappings: Record<string, string> = {};
          for (const pair of pairs) {
            if (pair.from && pair.to) mappings[pair.from] = pair.to;
          }
          onBack(mappings);
        }}>
          Back
        </Button>
        <Button size="sm" onClick={handleSubmit} disabled={isSubmitting}>
          {isSubmitting ? "Creating..." : "Create Rule"}
        </Button>
      </div>
    </div>
  );
}
