import { useState } from "react";
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
import type { MarketplaceProvider } from "@/types/marketplace";

interface SubscribeSheetProps {
  provider: MarketplaceProvider | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (providerId: string) => void;
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

  function handleOpenChange(next: boolean) {
    if (!next) setAccepted(false);
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
            Please review and accept before subscribing.
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-3 px-4 py-2">
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
            disabled={!accepted || isLoading}
            onClick={() => provider && onConfirm(provider.id)}
          >
            {isLoading ? "Subscribing..." : "Confirm"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
