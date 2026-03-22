import { useEffect, useState } from "react";
import { Loader2, Play, X } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { ActionRow } from "@/components/forms/action-row";
import {
  getActionsForDestination,
  getUnsupportedForDestination,
} from "@/lib/action-definitions";
import { useUpdateRule } from "@/hooks/use-routing-rules";
import { useParsePreview, type ParsePreviewResult } from "@/hooks/use-parse-preview";
import type { RoutingRuleResponse } from "@/types/api";

interface Props {
  rule: RoutingRuleResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandReferenceDrawer({ rule, open, onOpenChange }: Props) {
  const actions = getActionsForDestination(rule.destination_type);
  const unsupported = getUnsupportedForDestination(rule.destination_type);
  const entryActions = actions.filter((a) => a.isEntry);
  const optionalActions = actions.filter((a) => !a.isEntry);

  const allKeys = actions.map((a) => a.key);

  // Local optimistic state — prevents race conditions when toggling rapidly.
  // Syncs from server when rule prop updates (after query invalidation).
  const [localEnabled, setLocalEnabled] = useState<Set<string>>(
    () => new Set(rule.enabled_actions ?? allKeys),
  );

  // Sync local state when the server-side rule data updates
  useEffect(() => {
    setLocalEnabled(new Set(rule.enabled_actions ?? allKeys));
  }, [rule.enabled_actions]);  // eslint-disable-line react-hooks/exhaustive-deps

  const updateRule = useUpdateRule();
  const parsePreview = useParsePreview();

  const [testMessage, setTestMessage] = useState("");
  const [previewResult, setPreviewResult] = useState<ParsePreviewResult | null>(null);

  const enabledOptionalCount = optionalActions.filter((a) => localEnabled.has(a.key)).length;

  function handleToggle(key: string) {
    // Optimistic local update — no stale reads on rapid toggles
    const newEnabled = new Set(localEnabled);
    if (newEnabled.has(key)) {
      newEnabled.delete(key);
    } else {
      newEnabled.add(key);
    }

    // Always include entry actions
    for (const a of entryActions) {
      newEnabled.add(a.key);
    }

    setLocalEnabled(newEnabled);

    updateRule.mutate(
      { id: rule.id, data: { enabled_actions: Array.from(newEnabled) } },
      {
        onError: (err) => {
          // Revert to server state on failure
          setLocalEnabled(new Set(rule.enabled_actions ?? allKeys));
          toast.error(
            err instanceof Error ? err.message : "Failed to save. Reverted.",
          );
        },
      },
    );
  }

  function handleTestCommand() {
    if (!testMessage.trim()) return;
    setPreviewResult(null);
    parsePreview.mutate(
      { message: testMessage.trim(), destination_type: rule.destination_type },
      {
        onSuccess: (result) => setPreviewResult(result),
        onError: (err) => {
          toast.error(
            err instanceof Error ? err.message : "Couldn't parse this message.",
          );
        },
      },
    );
  }

  // Map parser action to a human-readable label
  function getActionLabel(action: string | null): string {
    if (!action) return "Unknown";
    const match = actions.find((a) => {
      // Map parser actions to action definition keys
      const keyMap: Record<string, string[]> = {
        entry: [
          "start_long_market_deal",
          "start_short_market_deal",
          "start_long_limit_deal",
          "start_short_limit_deal",
        ],
        close_position: ["close_order_at_market_price"],
        partial_close: ["partially_close_by_percentage", "partially_close_by_lot"],
        breakeven: ["move_sl_to_breakeven"],
        extra_order: ["open_extra_order"],
        close_all: ["close_all_orders_at_market_price"],
        close_all_stop: ["close_all_orders_at_market_price_and_stop_assist"],
        start_assist: ["start_assist"],
        stop_assist: ["stop_assist"],
      };
      return keyMap[action]?.includes(a.key);
    });
    return match?.label ?? action;
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[420px] flex flex-col"
        aria-label={`Signal Commands for ${rule.rule_name || rule.source_channel_name || "route"}`}
      >
        <SheetHeader className="shrink-0 space-y-1.5">
          <SheetTitle className="text-sm">Signal Commands</SheetTitle>
          <p className="text-[11px] text-muted-foreground">
            {rule.rule_name || rule.source_channel_name || rule.source_channel_id}
            {" · "}
            {rule.destination_type === "sagemaster_forex"
              ? "SageMaster Forex"
              : "SageMaster Crypto"}
          </p>
          <p className="text-[11px] text-muted-foreground/70 leading-relaxed">
            These are the Telegram messages this route understands.
            Toggle optional commands on or off — changes save instantly.
          </p>
        </SheetHeader>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto space-y-4 pr-1">
          {/* Required Commands */}
          <div>
            <div className="mb-2">
              <Label className="text-xs font-semibold block">
                Entry Signals
              </Label>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                Always forwarded — these open new trades
              </p>
            </div>
            <div className="space-y-1.5 mt-2">
              {entryActions.map((action) => (
                <ActionRow
                  key={action.key}
                  action={action}
                  isEnabled={true}
                  showCopy
                  readOnly
                />
              ))}
            </div>
          </div>

          {/* Optional Commands */}
          <div>
            <div className="mb-2">
              <Label className="text-xs font-semibold block">
                Management Signals
                <span className="ml-2 text-[10px] font-normal text-muted-foreground">
                  {enabledOptionalCount}/{optionalActions.length} active
                </span>
              </Label>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                Close, modify, or control trades — toggle each on or off
              </p>
            </div>
            <div className="space-y-1.5 mt-2">
              {optionalActions.map((action) => (
                <ActionRow
                  key={action.key}
                  action={action}
                  isEnabled={localEnabled.has(action.key)}
                  onToggle={handleToggle}
                  showCopy
                />
              ))}
            </div>
          </div>

          {/* Not Supported */}
          {unsupported.length > 0 && (
            <div>
              <div className="mb-2">
                <Label className="text-xs font-semibold block text-muted-foreground">
                  Not Supported
                </Label>
                <p className="text-[10px] text-muted-foreground/70 mt-0.5">
                  Platform limitations — these messages will be ignored
                </p>
              </div>
              <div className="space-y-1.5 mt-2">
                {unsupported.map((item) => (
                  <div
                    key={item.label}
                    className="rounded-md border border-border/50 bg-muted/20 px-3 py-2 opacity-60"
                  >
                    <div className="flex items-center gap-2">
                      <X className="h-3 w-3 text-muted-foreground shrink-0" />
                      <span className="text-xs text-muted-foreground">
                        {item.label}
                      </span>
                    </div>
                    <p className="text-[10px] text-muted-foreground/70 ml-5 mt-0.5">
                      {item.reason}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Test a Command — sticky footer */}
        <div className="shrink-0 border-t pt-3 mt-3 space-y-2">
          <div>
            <Label className="text-xs font-semibold block">
              Test a Command
            </Label>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              Paste a Telegram message to see how the AI parser interprets it
            </p>
          </div>
          <div className="flex gap-2">
            <Input
              type="text"
              placeholder="Paste a signal message..."
              value={testMessage}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setTestMessage(e.target.value)
              }
              onKeyDown={(e: React.KeyboardEvent) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleTestCommand();
                }
              }}
              maxLength={2000}
              className="h-8 text-sm flex-1"
              disabled={parsePreview.isPending}
            />
            <Button
              type="button"
              size="sm"
              className="h-8 px-3"
              onClick={handleTestCommand}
              disabled={!testMessage.trim() || parsePreview.isPending}
            >
              {parsePreview.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5" />
              )}
            </Button>
          </div>

          {parsePreview.isPending && (
            <p className="text-[10px] text-muted-foreground">Parsing signal...</p>
          )}

          {previewResult && (
            <div
              className={
                previewResult.is_valid_signal
                  ? "rounded-md border border-primary/30 bg-primary/5 px-3 py-2 space-y-1"
                  : "rounded-md border border-border bg-muted/30 px-3 py-2 space-y-1"
              }
            >
              {previewResult.is_valid_signal ? (
                <>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-primary">
                      {getActionLabel(previewResult.action)}
                    </span>
                    {previewResult.symbol && (
                      <span className="text-[10px] text-muted-foreground">
                        {previewResult.symbol}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                    {previewResult.direction && (
                      <span className="text-[10px] text-muted-foreground">
                        Direction: {previewResult.direction}
                      </span>
                    )}
                    {previewResult.entry_price != null && (
                      <span className="text-[10px] text-muted-foreground">
                        Entry: {previewResult.entry_price}
                      </span>
                    )}
                    {previewResult.stop_loss != null && (
                      <span className="text-[10px] text-muted-foreground">
                        SL: {previewResult.stop_loss}
                      </span>
                    )}
                    {previewResult.take_profits.length > 0 && (
                      <span className="text-[10px] text-muted-foreground">
                        TP: {previewResult.take_profits.join(", ")}
                      </span>
                    )}
                    {previewResult.percentage != null && (
                      <span className="text-[10px] text-muted-foreground">
                        {previewResult.percentage}%
                      </span>
                    )}
                  </div>
                </>
              ) : (
                <p className="text-[10px] text-muted-foreground">
                  {previewResult.ignore_reason ||
                    "No signal detected in this message. Try a trading command like \"Buy XAUUSD\"."}
                </p>
              )}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
