import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, X } from "lucide-react";
import { useUpdateRule } from "@/hooks/use-routing-rules";
import { apiFetch } from "@/lib/api";
import { toast } from "sonner";
import { usePageTitle } from "@/hooks/use-page-title";
import type { RoutingRuleResponse } from "@/types/api";

export function RoutingRulesEditPage() {
  usePageTitle("Edit Rule");
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const updateRule = useUpdateRule();

  const { data: rule, isLoading } = useQuery({
    queryKey: ["routing-rule", id],
    queryFn: () => apiFetch<RoutingRuleResponse>(`/routing-rules/${id}`),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">Edit Routing Rule</h1>
        <Card className="max-w-2xl">
          <CardContent className="pt-6">
            <div className="space-y-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!rule) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">Edit Routing Rule</h1>
        <p className="text-muted-foreground">Rule not found.</p>
        <Button variant="outline" onClick={() => navigate("/routing-rules")}>
          Back to Rules
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Edit Routing Rule</h1>
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>
            {rule.source_channel_name || rule.source_channel_id}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <EditRuleForm
            rule={rule}
            onSubmit={async (data) => {
              try {
                await updateRule.mutateAsync({ id: rule.id, data });
                toast.success("Rule updated");
                navigate("/routing-rules");
              } catch (err) {
                toast.error(
                  err instanceof Error ? err.message : "Failed to update rule"
                );
              }
            }}
            isSubmitting={updateRule.isPending}
            onCancel={() => navigate("/routing-rules")}
          />
        </CardContent>
      </Card>
    </div>
  );
}

interface EditRuleFormProps {
  rule: RoutingRuleResponse;
  onSubmit: (data: {
    destination_webhook_url: string;
    payload_version: "V1" | "V2";
    symbol_mappings: Record<string, string>;
  }) => Promise<void>;
  isSubmitting: boolean;
  onCancel: () => void;
}

function EditRuleForm({ rule, onSubmit, isSubmitting, onCancel }: EditRuleFormProps) {
  const [url, setUrl] = useState(rule.destination_webhook_url);
  const [version, setVersion] = useState<"V1" | "V2">(
    rule.payload_version as "V1" | "V2"
  );
  const [urlError, setUrlError] = useState("");
  const [pairs, setPairs] = useState<{ from: string; to: string }[]>(() => {
    return Object.entries(rule.symbol_mappings).map(([from, to]) => ({
      from,
      to,
    }));
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

  async function handleSubmit() {
    try {
      new URL(url);
    } catch {
      setUrlError("Enter a valid URL (e.g., https://...)");
      return;
    }
    setUrlError("");

    const mappings: Record<string, string> = {};
    for (const pair of pairs) {
      if (pair.from && pair.to) {
        mappings[pair.from] = pair.to;
      }
    }

    await onSubmit({
      destination_webhook_url: url,
      payload_version: version,
      symbol_mappings: mappings,
    });
  }

  return (
    <div className="space-y-6">
      {/* Source Channel (read-only) */}
      <div className="space-y-2">
        <Label>Source Channel</Label>
        <Input
          value={rule.source_channel_name || rule.source_channel_id}
          disabled
          className="bg-muted"
        />
      </div>

      {/* Webhook URL */}
      <div className="space-y-2">
        <Label htmlFor="edit-webhook-url">Webhook URL</Label>
        <Input
          id="edit-webhook-url"
          type="url"
          value={url}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            setUrl(e.target.value);
            if (urlError) setUrlError("");
          }}
        />
        {urlError && (
          <p className="text-xs text-destructive">{urlError}</p>
        )}
      </div>

      {/* Payload Version */}
      <div className="space-y-2">
        <Label>Payload Version</Label>
        <RadioGroup
          value={version}
          onValueChange={(v: string) => setVersion(v as "V1" | "V2")}
        >
          <div className="flex items-center space-x-3 rounded-md border p-3">
            <RadioGroupItem value="V1" id="edit-v1" />
            <Label htmlFor="edit-v1" className="cursor-pointer">
              <span className="font-medium">V1</span>
              <span className="ml-2 text-xs text-muted-foreground">
                Static strategy trigger
              </span>
            </Label>
          </div>
          <div className="flex items-center space-x-3 rounded-md border p-3">
            <RadioGroupItem value="V2" id="edit-v2" />
            <Label htmlFor="edit-v2" className="cursor-pointer">
              <span className="font-medium">V2</span>
              <span className="ml-2 text-xs text-muted-foreground">
                Full signal with TP/SL
              </span>
            </Label>
          </div>
        </RadioGroup>
      </div>

      {/* Symbol Mappings */}
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
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                updatePair(i, "from", e.target.value)
              }
            />
            <span className="text-muted-foreground">&rarr;</span>
            <Input
              placeholder="Broker symbol (e.g., XAUUSD)"
              value={pair.to}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                updatePair(i, "to", e.target.value)
              }
            />
            <Button variant="ghost" size="icon" onClick={() => removePair(i)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        ))}

        <Button variant="outline" size="sm" onClick={addPair}>
          <Plus className="mr-2 h-4 w-4" />
          Add Mapping
        </Button>
      </div>

      {/* Actions */}
      <div className="flex gap-2 pt-4">
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} disabled={isSubmitting || !url}>
          {isSubmitting ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </div>
  );
}
