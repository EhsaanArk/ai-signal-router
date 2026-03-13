import { useState } from "react";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Props {
  onFinish: (mappings: Record<string, string>) => void;
  onBack: () => void;
  isSubmitting: boolean;
}

export function StepSymbolMappings({ onFinish, onBack, isSubmitting }: Props) {
  const [pairs, setPairs] = useState<{ from: string; to: string }[]>([]);

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
    <div className="space-y-4">
      <div>
        <Label>Symbol Mappings (optional)</Label>
        <p className="text-xs text-muted-foreground mt-1">
          Map signal symbols to your broker's symbol names.
        </p>
      </div>

      {pairs.map((pair, i) => (
        <div key={i} className="flex items-center gap-2">
          <Input
            placeholder="Signal symbol (e.g., GOLD)"
            value={pair.from}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => updatePair(i, "from", e.target.value)}
          />
          <span className="text-muted-foreground">→</span>
          <Input
            placeholder="Broker symbol (e.g., XAUUSD)"
            value={pair.to}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => updatePair(i, "to", e.target.value)}
          />
          <Button
            variant="ghost"
            size="icon"
            onClick={() => removePair(i)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      ))}

      <Button variant="outline" size="sm" onClick={addPair}>
        <Plus className="mr-2 h-4 w-4" />
        Add Mapping
      </Button>

      <div className="flex gap-2 pt-4">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button onClick={handleSubmit} disabled={isSubmitting}>
          {isSubmitting ? "Creating..." : "Create Rule"}
        </Button>
      </div>
    </div>
  );
}
