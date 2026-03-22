import { useEffect, useState } from "react";
import {
  AlertTriangle, ArrowRight, Check, ChevronDown, ChevronRight,
  Copy, Info, Loader2, Send, Shield, ShieldAlert, ShieldCheck, ShieldX, X, Zap,
} from "lucide-react";
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
  getActionsForDestination,
  getExamplesForDestination,
  getUnsupportedForDestination,
  RISK_CONFIG,
  type ActionDefinition,
  type RiskLevel,
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
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="shrink-0 p-1 text-muted-foreground/40 hover:text-foreground transition-colors rounded"
      aria-label="Copy example"
    >
      {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
    </button>
  );
}

function RiskBadge({ risk }: { risk: RiskLevel }) {
  const cfg = RISK_CONFIG[risk];
  const Icon = risk === "destructive" ? ShieldAlert : risk === "caution" ? AlertTriangle : Shield;
  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border", cfg.bg, cfg.color, cfg.border)}>
      <Icon className="h-3 w-3" />
      {cfg.label}
    </span>
  );
}

function ActionCard({
  action,
  isEnabled,
  onToggle,
  readOnly,
  destinationType,
}: {
  action: ActionDefinition;
  isEnabled: boolean;
  onToggle?: (key: string) => void;
  readOnly?: boolean;
  destinationType: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const examples = getExamplesForDestination(action, destinationType);
  const riskCfg = RISK_CONFIG[action.risk];

  return (
    <div className={cn(
      "rounded-lg border transition-all",
      !isEnabled && "opacity-40",
      action.risk === "destructive" && isEnabled && "border-red-500/20",
      action.risk === "caution" && isEnabled && "border-amber-500/15",
    )}>
      {/* Header row */}
      <div className="flex items-center gap-3 px-4 py-3">
        <div className="shrink-0 w-10">
          {readOnly ? (
            <span className="text-[10px] text-emerald-500 font-semibold">ALWAYS</span>
          ) : (
            <Switch
              checked={isEnabled}
              onCheckedChange={() => onToggle?.(action.key)}
              className="scale-90"
              aria-label={`${action.label}: ${isEnabled ? "enabled" : "disabled"}`}
            />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold">{action.label}</span>
            <RiskBadge risk={action.risk} />
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">{action.description}</p>
        </div>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="shrink-0 p-1 text-muted-foreground hover:text-foreground transition-colors rounded"
        >
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>
      </div>

      {expanded && (
        <div className="border-t px-4 py-3 space-y-3 bg-muted/20">
          <div>
            <div className="flex items-center gap-1.5 mb-1">
              <Info className="h-3 w-3 text-muted-foreground" />
              <span className="text-[10px] font-semibold uppercase text-muted-foreground tracking-wider">When this happens</span>
            </div>
            <p className="text-xs text-foreground/80 leading-relaxed">{action.scenario}</p>
          </div>
          <div>
            <div className="flex items-center gap-1.5 mb-1">
              <Zap className={cn("h-3 w-3", riskCfg.color)} />
              <span className="text-[10px] font-semibold uppercase text-muted-foreground tracking-wider">What happens on your account</span>
            </div>
            <p className={cn("text-xs leading-relaxed", action.risk === "destructive" ? "text-red-400" : "text-foreground/80")}>
              {action.effect}
            </p>
          </div>
          <div>
            <span className="text-[10px] font-semibold uppercase text-muted-foreground tracking-wider">
              Example Telegram messages
            </span>
            <div className="mt-1.5 grid gap-1">
              {examples.map((ex, i) => (
                <div key={i} className="flex items-center gap-2 group">
                  <code className="flex-1 text-xs font-mono bg-muted/60 px-2.5 py-1.5 rounded border border-border/30">
                    {ex}
                  </code>
                  <CopyButton text={ex} />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function CommandReferenceDrawer({ rule, open, onOpenChange }: Props) {
  const actions = getActionsForDestination(rule.destination_type);
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

  const isCrypto = rule.destination_type === "sagemaster_crypto";
  const sandboxPlaceholder = isCrypto
    ? 'Try: "Buy BTC/USDT" or "Close 50%"'
    : 'Try: "Buy XAUUSD SL 2300 TP 2350"';

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-full md:max-w-[85vw] lg:max-w-[75vw] xl:max-w-[65vw] flex flex-col p-0"
        aria-label={`Signal Commands for ${rule.rule_name || rule.source_channel_name || "route"}`}
      >
        <div className="shrink-0 border-b px-6 py-4">
          <SheetHeader className="space-y-1">
            <SheetTitle className="text-base">Signal Command Reference</SheetTitle>
            <p className="text-xs text-muted-foreground">
              {rule.rule_name || rule.source_channel_name || rule.source_channel_id}
              {" · "}
              {isCrypto ? "SageMaster Crypto" : "SageMaster Forex"}
            </p>
          </SheetHeader>
          <div className="rounded-md bg-muted/30 border border-border/50 px-4 py-2.5 mt-3">
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <span className="font-medium text-foreground/70">How it works:</span>
              <span className="bg-muted px-2 py-0.5 rounded font-mono">Telegram message</span>
              <ArrowRight className="h-3 w-3 shrink-0" />
              <span className="bg-muted px-2 py-0.5 rounded">Sage Intelligence</span>
              <ArrowRight className="h-3 w-3 shrink-0" />
              <span className="bg-primary/10 text-primary px-2 py-0.5 rounded font-medium">Webhook Action</span>
              <ArrowRight className="h-3 w-3 shrink-0" />
              <span className="bg-muted px-2 py-0.5 rounded">SageMaster</span>
            </div>
            <p className="text-[10px] text-muted-foreground/70 mt-1.5">
              Your signal provider sends a message in Telegram. Sage Intelligence identifies the action
              and routes it to your SageMaster account. Click any action below to see example messages and what happens.
            </p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold">Entry Signals</h3>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Open new positions. These are always active — every trade starts with an entry.
                </p>
              </div>
              <span className="text-[10px] text-emerald-500 font-semibold bg-emerald-500/10 px-2 py-1 rounded-full">Always active</span>
            </div>
            <div className="grid gap-2">
              {entryActions.map((action) => (
                <ActionCard key={action.key} action={action} isEnabled={true} readOnly destinationType={rule.destination_type} />
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold">Trade Management Signals</h3>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Manage open positions — close, partial close, breakeven, etc. Toggle each action on or off.
                </p>
              </div>
              <span className="text-[10px] text-muted-foreground font-medium">
                {enabledOptionalCount}/{optionalActions.length} active
              </span>
            </div>
            <div className="grid gap-2">
              {optionalActions.map((action) => (
                <ActionCard
                  key={action.key}
                  action={action}
                  isEnabled={localEnabled.has(action.key)}
                  onToggle={handleToggle}
                  destinationType={rule.destination_type}
                />
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3">
            <div className="flex items-start gap-2">
              <ShieldAlert className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-semibold text-red-500">About destructive actions</p>
                <p className="text-[11px] text-muted-foreground mt-1 leading-relaxed">
                  Actions marked <span className="text-red-500 font-medium">Destructive</span> close positions at market price immediately.
                  They are <span className="font-medium text-foreground">irreversible</span> — once executed, the trade is closed and cannot be reopened at the same price.
                  If you&apos;re unsure whether your signal provider sends these commands, consider disabling them
                  until you&apos;ve verified their signal format using the test sandbox below.
                </p>
              </div>
            </div>
          </div>

          {unsupported.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-muted-foreground mb-2">Not Supported by SageMaster</h3>
              <div className="space-y-1.5">
                {unsupported.map((item) => (
                  <div key={item.label} className="flex items-start gap-2 py-1.5 opacity-60">
                    <X className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />
                    <div>
                      <span className="text-xs text-muted-foreground">{item.label}</span>
                      <p className="text-[10px] text-muted-foreground/60">{item.reason}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="shrink-0 border-t px-6 py-4 space-y-3 bg-background">
          <div className="flex items-center gap-2">
            <Send className="h-4 w-4 text-primary shrink-0" />
            <div>
              <h3 className="text-sm font-semibold">Test a Signal</h3>
              <p className="text-[10px] text-muted-foreground">
                Paste a real message from your signal provider to see exactly how it would be routed.
              </p>
            </div>
          </div>
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
              className="h-10 text-sm flex-1 font-mono"
              disabled={parsePreview.isPending}
            />
            <Button type="button" size="sm" className="h-10 px-5" onClick={handleTestCommand} disabled={!testMessage.trim() || parsePreview.isPending}>
              {parsePreview.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Simulate"}
            </Button>
          </div>

          {parsePreview.isPending && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Running through Sage Intelligence...
            </div>
          )}

          {previewResult && (
            <div className={cn(
              "rounded-lg border px-4 py-3",
              previewResult.is_valid_signal ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5",
            )}>
              {previewResult.is_valid_signal ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <code className="text-xs font-mono bg-muted px-2 py-1 rounded max-w-[200px] truncate">{testMessage}</code>
                    <ArrowRight className="h-3 w-3 text-emerald-500 shrink-0" />
                    <span className="text-sm font-semibold text-emerald-500">{getActionLabel(previewResult.action)}</span>
                  </div>

                  {previewResult.route_would_forward != null && (
                    <div className={cn(
                      "flex items-center gap-1.5 text-[10px] font-medium rounded px-2 py-1",
                      previewResult.route_would_forward ? "bg-emerald-500/10 text-emerald-600" : "bg-red-500/10 text-red-500",
                    )}>
                      {previewResult.route_would_forward ? (
                        <><ShieldCheck className="h-3 w-3 shrink-0" /> Would be forwarded to webhook</>
                      ) : (
                        <><ShieldX className="h-3 w-3 shrink-0" /> {previewResult.blocked_reason || "Blocked by action filter"}</>
                      )}
                    </div>
                  )}

                  <div className="grid grid-cols-3 gap-x-4 gap-y-1">
                    {previewResult.symbol && (<div><span className="text-[9px] uppercase text-muted-foreground">Symbol</span><p className="text-xs font-medium">{previewResult.symbol}</p></div>)}
                    {previewResult.direction && (<div><span className="text-[9px] uppercase text-muted-foreground">Direction</span><p className="text-xs font-medium capitalize">{previewResult.direction}</p></div>)}
                    {previewResult.entry_price != null && (<div><span className="text-[9px] uppercase text-muted-foreground">Entry Price</span><p className="text-xs font-medium">{previewResult.entry_price}</p></div>)}
                    {previewResult.stop_loss != null && (<div><span className="text-[9px] uppercase text-muted-foreground">Stop Loss</span><p className="text-xs font-medium">{previewResult.stop_loss}</p></div>)}
                    {previewResult.take_profits.length > 0 && (<div><span className="text-[9px] uppercase text-muted-foreground">Take Profit</span><p className="text-xs font-medium">{previewResult.take_profits.join(", ")}</p></div>)}
                    {previewResult.percentage != null && (<div><span className="text-[9px] uppercase text-muted-foreground">Percentage</span><p className="text-xs font-medium">{previewResult.percentage}%</p></div>)}
                  </div>

                  <button type="button" onClick={() => copyText(JSON.stringify(previewResult, null, 2), "Parsed result copied")} className="text-[10px] text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1">
                    <Copy className="h-2.5 w-2.5" /> Copy parsed result
                  </button>
                </div>
              ) : (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-amber-500">Not recognized as a trading signal</p>
                  <p className="text-[11px] text-muted-foreground">{previewResult.ignore_reason || "The Sage Intelligence couldn't identify a trading action in this message."}</p>
                  <p className="text-[11px] text-muted-foreground/60">
                    Try something like: <code className="bg-muted px-1.5 py-0.5 rounded font-mono">{isCrypto ? "Buy BTC/USDT" : "Buy XAUUSD SL 2300 TP 2350"}</code>
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
