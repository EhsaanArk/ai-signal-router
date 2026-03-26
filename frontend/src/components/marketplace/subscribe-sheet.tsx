import { useState } from "react";
import { Loader2 } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useRoutingRules, useCreateRule } from "@/hooks/use-routing-rules";
import type { MarketplaceProvider } from "@/types/marketplace";

interface SubscribeSheetProps {
  provider: MarketplaceProvider | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (providerId: string, webhookDestinationId: string) => void;
  isLoading: boolean;
}

export function SubscribeSheet({
  provider,
  open,
  onOpenChange,
  onConfirm,
  isLoading,
}: SubscribeSheetProps) {
  const [accepted, setAccepted] = useState(false);
  const [selectedRuleId, setSelectedRuleId] = useState<string>("");
  const { data: rules, refetch: refetchRules } = useRoutingRules(open);
  const createRule = useCreateRule();

  // Inline destination creation state
  const [showInlineForm, setShowInlineForm] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [destLabel, setDestLabel] = useState("");

  // Only show active rules with a webhook URL configured
  const availableRules = rules?.filter((r) => r.is_active && r.destination_webhook_url) ?? [];

  function handleOpenChange(next: boolean) {
    if (!next) {
      setAccepted(false);
      setSelectedRuleId("");
      setShowInlineForm(false);
      setWebhookUrl("");
      setDestLabel("");
    }
    onOpenChange(next);
  }

  async function handleCreateDestination() {
    if (!webhookUrl.trim()) return;
    try {
      const newRule = await createRule.mutateAsync({
        source_channel_id: "marketplace-template",
        source_channel_name: "Marketplace Destination",
        destination_webhook_url: webhookUrl.trim(),
        payload_version: "V1",
        symbol_mappings: {},
        risk_overrides: {},
        rule_name: destLabel.trim() || "Marketplace Destination",
        destination_label: destLabel.trim() || "My Trading Account",
        destination_type: "sagemaster_forex",
        is_marketplace_template: true,
      } as any);
      await refetchRules();
      setSelectedRuleId(newRule.id);
      setShowInlineForm(false);
    } catch {
      // Error handled by mutation error state
    }
  }

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent side="bottom" className="rounded-t-xl max-h-[80vh] sm:max-w-lg sm:mx-auto">
        <SheetHeader>
          <SheetTitle className="text-lg font-bold">
            Subscribe to{" "}
            <span className="text-primary">{provider?.name ?? "Provider"}</span>
          </SheetTitle>
          <SheetDescription>
            Choose where signals should go and accept the disclaimer.
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-3 px-4 py-2">
          {/* Destination picker */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-foreground">
              Trading Destination
            </label>
            {availableRules.length === 0 && !showInlineForm ? (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  You haven&apos;t connected a trading account yet.
                </p>
                <p className="text-[10px] text-muted-foreground">
                  Paste your SageMaster webhook URL to start receiving signals.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  onClick={() => setShowInlineForm(true)}
                >
                  Connect Your Account
                </Button>
              </div>
            ) : showInlineForm ? (
              <div className="space-y-2 rounded-md border border-border/40 p-3">
                <div className="space-y-1">
                  <label className="text-[11px] text-muted-foreground">
                    Account Label
                  </label>
                  <Input
                    value={destLabel}
                    onChange={(e) => setDestLabel(e.target.value)}
                    placeholder="e.g. My SageMaster Account"
                    className="h-8 text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] text-muted-foreground">
                    Webhook URL
                  </label>
                  <Input
                    value={webhookUrl}
                    onChange={(e) => setWebhookUrl(e.target.value)}
                    placeholder="https://app.sagemaster.io/webhook/..."
                    className="h-8 text-xs font-mono"
                    type="url"
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs"
                    onClick={() => setShowInlineForm(false)}
                    disabled={createRule.isPending}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    className="text-xs"
                    disabled={!webhookUrl.trim() || createRule.isPending}
                    onClick={handleCreateDestination}
                  >
                    {createRule.isPending ? (
                      <>
                        <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      "Save Destination"
                    )}
                  </Button>
                </div>
                {createRule.isError && (
                  <p className="text-[10px] text-rose-400">
                    Failed to create destination. Check the URL and try again.
                  </p>
                )}
              </div>
            ) : (
              <>
                <Select value={selectedRuleId} onValueChange={setSelectedRuleId}>
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue placeholder="Select a destination..." />
                  </SelectTrigger>
                  <SelectContent>
                    {availableRules.map((rule) => (
                      <SelectItem key={rule.id} value={rule.id} className="text-xs">
                        {rule.destination_label || rule.rule_name || "Unnamed account"}
                        {rule.destination_type && (
                          <span className="text-muted-foreground ml-1">
                            ({rule.destination_type})
                          </span>
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <button
                  type="button"
                  className="text-[10px] text-primary hover:underline"
                  onClick={() => setShowInlineForm(true)}
                >
                  + Add a new destination
                </button>
              </>
            )}
            <p className="text-[10px] text-muted-foreground">
              Signals will be routed to this destination&apos;s webhook URL.
            </p>
          </div>

          {/* Disclaimer */}
          <ul className="space-y-2 text-xs text-muted-foreground list-disc pl-4">
            <li>
              Signals from this provider will be routed to your configured
              destinations. You are responsible for any trades placed.
            </li>
            <li>
              Past performance is not indicative of future results.
              Statistics shown are computed by Sage Intelligence and may not
              reflect real-time accuracy.
            </li>
            <li>
              You can unsubscribe at any time. Existing open positions will
              not be affected by unsubscribing.
            </li>
          </ul>

          <label className="flex items-start gap-2 cursor-pointer pt-2">
            <Checkbox
              checked={accepted}
              onCheckedChange={(v) => setAccepted(v === true)}
              className="mt-0.5"
            />
            <span className="text-xs leading-relaxed">
              I understand and accept the risks of subscribing to third-party
              signal providers.
            </span>
          </label>
        </div>

        <SheetFooter className="flex-row gap-2 px-4 pb-6 sm:pb-4">
          <Button
            variant="outline"
            size="sm"
            className="flex-1"
            onClick={() => handleOpenChange(false)}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            className="flex-1"
            disabled={!accepted || !selectedRuleId || isLoading}
            onClick={() => provider && onConfirm(provider.id, selectedRuleId)}
          >
            {isLoading ? "Subscribing..." : "Confirm"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
