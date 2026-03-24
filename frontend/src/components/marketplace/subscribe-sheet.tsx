import { useState } from "react";
import { useNavigate } from "react-router-dom";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useRoutingRules } from "@/hooks/use-routing-rules";
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
  const navigate = useNavigate();
  const [accepted, setAccepted] = useState(false);
  const [selectedRuleId, setSelectedRuleId] = useState<string>("");
  const { data: rules } = useRoutingRules(open);

  // Only show active rules with a webhook URL configured
  const availableRules = rules?.filter((r) => r.is_active && r.destination_webhook_url) ?? [];

  function handleOpenChange(next: boolean) {
    if (!next) {
      setAccepted(false);
      setSelectedRuleId("");
    }
    onOpenChange(next);
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
            Choose a destination and accept the disclaimer.
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-3 px-4 py-2">
          {/* Destination picker */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-foreground">
              Webhook Destination
            </label>
            {availableRules.length === 0 ? (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  No signal routes configured yet.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  onClick={() => {
                    onOpenChange(false);
                    navigate("/routing-rules/new");
                  }}
                >
                  Create a Signal Route
                </Button>
              </div>
            ) : (
              <Select value={selectedRuleId} onValueChange={setSelectedRuleId}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Select a destination..." />
                </SelectTrigger>
                <SelectContent>
                  {availableRules.map((rule) => (
                    <SelectItem key={rule.id} value={rule.id} className="text-xs">
                      {rule.destination_label || rule.rule_name || "Unnamed route"}
                      {rule.destination_type && (
                        <span className="text-muted-foreground ml-1">
                          ({rule.destination_type})
                        </span>
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
