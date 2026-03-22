import { useEffect, useState } from "react";
import { ArrowRight, Check, Copy, Loader2, Send, ShieldCheck, ShieldX, X } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import {
  getActionExamples,
  getUnsupportedForDestination,
  type ActionDefinition,
} from "@/lib/action-definitions";
import { useUpdateRule } from "@/hooks/use-routing-rules";
import { useParsePreview, type ParsePreviewResult } from "@/hooks/use-parse-preview";
import { useCopyToClipboard } from "@/hooks/use-clipboard";
import { cn } from "@/lib/utils";
import type { RoutingRuleResponse } from "@/types/api";

interface Props {
  rule: RoutingRuleResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard.writeText(text.replace(/^"|"$/g, "").split('", "')[0]);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="shrink-0 p-0.5 text-muted-foreground/50 hover:text-foreground transition-colors"
      aria-label="Copy example"
    >
      {copied ? <Check className="h-2.5 w-2.5 text-emerald-500" /> : <Copy className="h-2.5 w-2.5" />}
    </button>
  );
}

function CommandTableRow({
  action,
  isEnabled,
  onToggle,
  readOnly,
}: {
  action: ActionDefinition;
  isEnabled: boolean;
  onToggle?: (key: string) => void;
  readOnly?: boolean;
}) {
  return (
    <tr className={cn(
      "border-b border-border/40 transition-colors",
      !isEnabled && "opacity-40",
    )}>
      {/* On/Off */}
      <td className="py-2 pr-2 align-top">
        {readOnly ? (
          <span className="text-[10px] text-emerald-500 font-medium">ON</span>
        ) : (
          <Switch
            checked={isEnabled}
            onCheckedChange={() => onToggle?.(action.key)}
            className="scale-75 origin-left"
            aria-label={`${action.label}: ${isEnabled ? "enabled" : "disabled"}`}
          />
        )}
      </td>
      {/* Telegram message example */}
      <td className="py-2 pr-2 align-top">
        <div className="flex items-start gap-1">
          <code className="text-[11px] font-mono text-foreground/80 leading-snug">
            {action.example}
          </code>
          <CopyButton text={action.example} />
        </div>
      </td>
      {/* Arrow */}
      <td className="py-2 px-1 align-top">
        <ArrowRight className="h-3 w-3 text-muted-foreground/40 mt-0.5" />
      </td>
      {/* Webhook action */}
      <td className="py-2 align-top">
        <span className="text-[11px] font-medium">{action.label}</span>
        <p className="text-[10px] text-muted-foreground leading-snug mt-0.5">
          {action.description}
        </p>
      </td>
    </tr>
  );
}

export function CommandReferenceDrawer({ rule, open, onOpenChange }: Props) {
  const actions = getActionExamples(rule.destination_type);
  const unsupported = getUnsupportedForDestination(rule.destination_type);
  const entryActions = actions.filter((a) => a.isEntry);
  const optionalActions = actions.filter((a) => !a.isEntry);
  const allKeys = actions.map((a) => a.key);

  const [localEnabled, setLocalEnabled] = useState<Set<string>>(
    () => new Set(rule.enabled_actions ?? allKeys),
  );

  useEffect(() => {
    setLocalEnabled(new Set(rule.enabled_actions ?? allKeys));
  }, [rule.enabled_actions]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateRule = useUpdateRule();
  const parsePreview = useParsePreview();
  const [copyText] = useCopyToClipboard();
  const [testMessage, setTestMessage] = useState("");
  const [previewResult, setPreviewResult] = useState<ParsePreviewResult | null>(null);

  const enabledOptionalCount = optionalActions.filter((a) => localEnabled.has(a.key)).length;

  function handleToggle(key: string) {
    const newEnabled = new Set(localEnabled);
    if (newEnabled.has(key)) {
      newEnabled.delete(key);
    } else {
      newEnabled.add(key);
    }
    for (const a of entryActions) newEnabled.add(a.key);
    setLocalEnabled(newEnabled);

    updateRule.mutate(
      { id: rule.id, data: { enabled_actions: Array.from(newEnabled) } },
      {
        onError: (err) => {
          setLocalEnabled(new Set(rule.enabled_actions ?? allKeys));
          toast.error(err instanceof Error ? err.message : "Failed to save. Reverted.");
        },
      },
    );
  }

  function handleTestCommand() {
    if (!testMessage.trim()) return;
    setPreviewResult(null);
    parsePreview.mutate(
      {
        message: testMessage.trim(),
        destination_type: rule.destination_type,
        enabled_actions: rule.enabled_actions ?? null,
      },
      {
        onSuccess: (result) => setPreviewResult(result),
        onError: (err) => {
          toast.error(err instanceof Error ? err.message : "Couldn't parse this message.");
        },
      },
    );
  }

  function getActionLabel(action: string | null): string {
    if (!action) return "Unknown";
    const keyMap: Record<string, string[]> = {
      entry: ["start_long_market_deal", "start_short_market_deal", "start_long_limit_deal", "start_short_limit_deal"],
      close_position: ["close_order_at_market_price"],
      partial_close: ["partially_close_by_percentage", "partially_close_by_lot"],
      breakeven: ["move_sl_to_breakeven"],
      extra_order: ["open_extra_order"],
      close_all: ["close_all_orders_at_market_price"],
      close_all_stop: ["close_all_orders_at_market_price_and_stop_assist"],
      start_assist: ["start_assist"],
      stop_assist: ["stop_assist"],
    };
    const match = actions.find((a) => keyMap[action]?.includes(a.key));
    return match?.label ?? action;
  }

  // Prefill example for the sandbox based on destination type
  const sandboxPlaceholder = rule.destination_type === "sagemaster_crypto"
    ? 'Try: "Buy BTC/USDT" or "Close 50%"'
    : 'Try: "Buy XAUUSD SL 2300 TP 2350"';

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[480px] flex flex-col"
        aria-label={`Signal Commands for ${rule.rule_name || rule.source_channel_name || "route"}`}
      >
        <SheetHeader className="shrink-0 space-y-1">
          <SheetTitle className="text-sm">Signal Command Reference</SheetTitle>
          <p className="text-[11px] text-muted-foreground">
            {rule.rule_name || rule.source_channel_name || rule.source_channel_id}
            {" · "}
            {rule.destination_type === "sagemaster_forex" ? "SageMaster Forex" : "SageMaster Crypto"}
          </p>
        </SheetHeader>

        {/* How it works — visual flow */}
        <div className="shrink-0 rounded-md bg-muted/30 border border-border/50 px-3 py-2 mt-2">
          <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
            <span className="font-medium text-foreground/70">How it works:</span>
            <span className="bg-muted px-1.5 py-0.5 rounded font-mono">Telegram message</span>
            <ArrowRight className="h-3 w-3 shrink-0" />
            <span className="bg-muted px-1.5 py-0.5 rounded">AI Parser</span>
            <ArrowRight className="h-3 w-3 shrink-0" />
            <span className="bg-primary/10 text-primary px-1.5 py-0.5 rounded font-medium">Webhook Action</span>
          </div>
        </div>

        {/* Scrollable command tables */}
        <div className="flex-1 overflow-y-auto mt-3 space-y-5 pr-1">

          {/* Entry Signals — always on */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold">Entry Signals</h3>
              <span className="text-[10px] text-emerald-500 font-medium">Always active</span>
            </div>
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-border/60">
                  <th className="text-[9px] uppercase text-muted-foreground font-medium pb-1 w-8"></th>
                  <th className="text-[9px] uppercase text-muted-foreground font-medium pb-1">Message</th>
                  <th className="pb-1 w-5"></th>
                  <th className="text-[9px] uppercase text-muted-foreground font-medium pb-1">Action</th>
                </tr>
              </thead>
              <tbody>
                {entryActions.map((action) => (
                  <CommandTableRow key={action.key} action={action} isEnabled={true} readOnly />
                ))}
              </tbody>
            </table>
          </div>

          {/* Management Signals — toggleable */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold">Management Signals</h3>
              <span className="text-[10px] text-muted-foreground">
                {enabledOptionalCount}/{optionalActions.length} active
              </span>
            </div>
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-border/60">
                  <th className="text-[9px] uppercase text-muted-foreground font-medium pb-1 w-10"></th>
                  <th className="text-[9px] uppercase text-muted-foreground font-medium pb-1">Message</th>
                  <th className="pb-1 w-5"></th>
                  <th className="text-[9px] uppercase text-muted-foreground font-medium pb-1">Action</th>
                </tr>
              </thead>
              <tbody>
                {optionalActions.map((action) => (
                  <CommandTableRow
                    key={action.key}
                    action={action}
                    isEnabled={localEnabled.has(action.key)}
                    onToggle={handleToggle}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {/* Not Supported */}
          {unsupported.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-muted-foreground mb-2">Not Supported</h3>
              <div className="space-y-1">
                {unsupported.map((item) => (
                  <div key={item.label} className="flex items-start gap-2 py-1 opacity-50">
                    <X className="h-3 w-3 text-muted-foreground shrink-0 mt-0.5" />
                    <div>
                      <span className="text-[11px] text-muted-foreground">{item.label}</span>
                      <p className="text-[10px] text-muted-foreground/60">{item.reason}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Test Sandbox — sticky footer */}
        <div className="shrink-0 border-t pt-3 mt-2 space-y-2">
          <div className="flex items-center gap-2">
            <Send className="h-3.5 w-3.5 text-primary shrink-0" />
            <h3 className="text-xs font-semibold">Test a Signal</h3>
          </div>
          <p className="text-[10px] text-muted-foreground leading-relaxed">
            Type a message like your signal provider would send in Telegram.
            The AI parser will show you exactly what action it triggers.
          </p>
          <div className="flex gap-2">
            <Input
              type="text"
              placeholder={sandboxPlaceholder}
              value={testMessage}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTestMessage(e.target.value)}
              onKeyDown={(e: React.KeyboardEvent) => {
                if (e.key === "Enter") { e.preventDefault(); handleTestCommand(); }
              }}
              maxLength={2000}
              className="h-9 text-sm flex-1 font-mono"
              disabled={parsePreview.isPending}
            />
            <Button
              type="button"
              size="sm"
              className="h-9 px-4"
              onClick={handleTestCommand}
              disabled={!testMessage.trim() || parsePreview.isPending}
            >
              {parsePreview.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                "Parse"
              )}
            </Button>
          </div>

          {parsePreview.isPending && (
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              Running through AI parser...
            </div>
          )}

          {previewResult && (
            <div className={cn(
              "rounded-md border px-3 py-2.5",
              previewResult.is_valid_signal
                ? "border-emerald-500/30 bg-emerald-500/5"
                : "border-amber-500/30 bg-amber-500/5",
            )}>
              {previewResult.is_valid_signal ? (
                <div className="space-y-2">
                  {/* Visual flow: input → action */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <code className="text-[10px] font-mono bg-muted px-1.5 py-0.5 rounded max-w-[140px] truncate">
                      {testMessage}
                    </code>
                    <ArrowRight className="h-3 w-3 text-emerald-500 shrink-0" />
                    <span className="text-xs font-semibold text-emerald-500">
                      {getActionLabel(previewResult.action)}
                    </span>
                  </div>

                  {/* Forwarding verdict */}
                  {previewResult.route_would_forward != null && (
                    <div className={cn(
                      "flex items-center gap-1.5 text-[10px] font-medium rounded px-2 py-1",
                      previewResult.route_would_forward
                        ? "bg-emerald-500/10 text-emerald-600"
                        : "bg-red-500/10 text-red-500",
                    )}>
                      {previewResult.route_would_forward ? (
                        <>
                          <ShieldCheck className="h-3 w-3 shrink-0" />
                          Would be forwarded to webhook
                        </>
                      ) : (
                        <>
                          <ShieldX className="h-3 w-3 shrink-0" />
                          {previewResult.blocked_reason || "Blocked by action filter"}
                        </>
                      )}
                    </div>
                  )}

                  {/* Parsed details */}
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                    {previewResult.symbol && (
                      <div>
                        <span className="text-[9px] uppercase text-muted-foreground">Symbol</span>
                        <p className="text-[11px] font-medium">{previewResult.symbol}</p>
                      </div>
                    )}
                    {previewResult.direction && (
                      <div>
                        <span className="text-[9px] uppercase text-muted-foreground">Direction</span>
                        <p className="text-[11px] font-medium capitalize">{previewResult.direction}</p>
                      </div>
                    )}
                    {previewResult.entry_price != null && (
                      <div>
                        <span className="text-[9px] uppercase text-muted-foreground">Entry Price</span>
                        <p className="text-[11px] font-medium">{previewResult.entry_price}</p>
                      </div>
                    )}
                    {previewResult.stop_loss != null && (
                      <div>
                        <span className="text-[9px] uppercase text-muted-foreground">Stop Loss</span>
                        <p className="text-[11px] font-medium">{previewResult.stop_loss}</p>
                      </div>
                    )}
                    {previewResult.take_profits.length > 0 && (
                      <div>
                        <span className="text-[9px] uppercase text-muted-foreground">Take Profit</span>
                        <p className="text-[11px] font-medium">{previewResult.take_profits.join(", ")}</p>
                      </div>
                    )}
                    {previewResult.percentage != null && (
                      <div>
                        <span className="text-[9px] uppercase text-muted-foreground">Percentage</span>
                        <p className="text-[11px] font-medium">{previewResult.percentage}%</p>
                      </div>
                    )}
                  </div>

                  {/* Copy parsed JSON */}
                  <button
                    type="button"
                    onClick={() => copyText(JSON.stringify(previewResult, null, 2), "Parsed result copied")}
                    className="text-[10px] text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
                  >
                    <Copy className="h-2.5 w-2.5" /> Copy parsed result
                  </button>
                </div>
              ) : (
                <div className="space-y-1">
                  <p className="text-[11px] font-medium text-amber-500">Not recognized as a signal</p>
                  <p className="text-[10px] text-muted-foreground">
                    {previewResult.ignore_reason || "The AI parser couldn't identify a trading action in this message."}
                  </p>
                  <p className="text-[10px] text-muted-foreground/60">
                    Try something like: <code className="bg-muted px-1 py-0.5 rounded font-mono">{
                      rule.destination_type === "sagemaster_crypto" ? "Buy BTC/USDT" : "Buy XAUUSD SL 2300 TP 2350"
                    }</code>
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
