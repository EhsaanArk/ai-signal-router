import { useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Circle,
  Copy,
  FlaskConical,
  Loader2,
  Reply,
  Route,
  XCircle,
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useCopyToClipboard } from "@/hooks/use-clipboard";
import { useReplaySignal } from "@/hooks/use-admin-parser";
import { useRoutingRules } from "@/hooks/use-routing-rules";
import { useAuth } from "@/contexts/auth-context";
import { cn, humanizeAction } from "@/lib/utils";
import type { ReplayResponse, RoutingRuleResponse, SignalLogResponse, ValidationCheck } from "@/types/api";

interface Props {
  log: SignalLogResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface PipelineStep {
  label: string;
  detail: string;
  status: "done" | "failed" | "skipped";
}

function humanizeErrorMessage(msg: string): string {
  if (msg === "Not an actionable trade signal." || msg === "Not an actionable trade signal") {
    return "Sage Intelligence: message too brief or ambiguous to extract a trade signal";
  }

  const assetMatch = msg.match(/Signal asset class '(.+?)' is not supported by (.+?) destinations/);
  if (assetMatch) {
    return `Asset mismatch: ${assetMatch[1]} signals can't be routed to ${assetMatch[2]} destinations`;
  }

  const actionMatch = msg.match(/Action '(.+?)' is not enabled for this route/);
  if (actionMatch) {
    return `Action disabled: "${actionMatch[1]}" is turned off in this route's settings`;
  }

  const symbolMatch = msg.match(/Symbol '(.+?)' is blacklisted/);
  if (symbolMatch) {
    return `Symbol blocked: "${symbolMatch[1]}" is in this route's keyword blacklist`;
  }

  return msg;
}

function getReceivedStepDetail(
  log: SignalLogResponse,
  matchedRule: RoutingRuleResponse | null,
): string {
  if (matchedRule) {
    const ruleName = matchedRule.rule_name || matchedRule.source_channel_name || "Rule";
    const destLabel = matchedRule.destination_label
      || destinationTypeLabel(matchedRule.destination_type);
    return `Rule: ${ruleName} → ${destLabel}`;
  }
  return log.channel_id || "Source channel";
}

function destinationTypeLabel(type: string): string {
  switch (type) {
    case "sagemaster_forex": return "SageMaster Forex";
    case "sagemaster_crypto": return "SageMaster Crypto";
    case "custom": return "Custom";
    default: return type;
  }
}

function getPipelineSteps(
  log: SignalLogResponse,
  matchedRule: RoutingRuleResponse | null,
): PipelineStep[] {
  const steps: PipelineStep[] = [];

  steps.push({
    label: "Signal Received",
    detail: getReceivedStepDetail(log, matchedRule),
    status: "done",
  });

  if (log.status === "ignored") {
    const isParserRejection = !log.routing_rule_id;
    steps.push({
      label: isParserRejection ? "Sage Intelligence Filtered" : "Rule Rejected",
      detail: humanizeErrorMessage(log.error_message || "Ignored"),
      status: "skipped",
    });
    return steps;
  }

  steps.push({
    label: "Sage Intelligence",
    detail: log.parsed_data
      ? `${(log.parsed_data.action as string) || "entry"} ${(log.parsed_data.symbol as string) || ""}`
      : "Parsing completed",
    status: log.parsed_data ? "done" : "failed",
  });

  if (log.webhook_payload) {
    steps.push({
      label: "Webhook Dispatched",
      detail: "Payload sent to destination",
      status: "done",
    });
  }

  steps.push({
    label: log.status === "success" ? "Routed" : "Failed",
    detail: log.status === "success"
      ? new Date(log.processed_at).toLocaleString()
      : humanizeErrorMessage(log.error_message || "Unknown error"),
    status: log.status === "success" ? "done" : "failed",
  });

  return steps;
}

function DataField({ label, value, mono }: { label: string; value: string | null | undefined; mono?: boolean }) {
  if (!value) return null;
  return (
    <div>
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
      <p className={cn("text-xs mt-0.5", mono && "font-mono font-tabular")}>{value}</p>
    </div>
  );
}

function ReplayComparison({ replay }: { replay: ReplayResponse }) {
  const original = replay.original_parsed;
  const newParsed = replay.new_parsed;

  // Find fields that differ
  const allKeys = new Set([
    ...Object.keys(original || {}),
    ...Object.keys(newParsed),
  ]);
  const diffs: { key: string; old: unknown; new_: unknown }[] = [];
  const same: { key: string; value: unknown }[] = [];

  for (const key of allKeys) {
    const oldVal = original?.[key];
    const newVal = newParsed[key];
    if (JSON.stringify(oldVal) !== JSON.stringify(newVal)) {
      diffs.push({ key, old: oldVal, new_: newVal });
    } else {
      same.push({ key, value: newVal });
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="text-[10px]">
          {replay.model_used}
        </Badge>
        <Badge variant="outline" className="text-[10px]">
          temp: {replay.temperature_used}
        </Badge>
      </div>

      {/* Validation checks */}
      {replay.validation_checks.length > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Validation</p>
          {replay.validation_checks.map((check: ValidationCheck, i: number) => (
            <div key={i} className="flex items-start gap-1.5 text-[11px]">
              {check.passed ? (
                <CheckCircle2 className="h-3 w-3 text-emerald-500 mt-0.5 shrink-0" />
              ) : (
                <XCircle className="h-3 w-3 text-rose-500 mt-0.5 shrink-0" />
              )}
              <span className={check.passed ? "text-muted-foreground" : "text-rose-600"}>
                {check.name}: {check.message}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Differences */}
      {diffs.length > 0 ? (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">
            Changed Fields ({diffs.length})
          </p>
          <div className="space-y-1.5">
            {diffs.map((d) => (
              <div key={d.key} className="rounded bg-muted p-2 text-[11px]">
                <span className="font-mono font-medium">{d.key}</span>
                <div className="flex gap-3 mt-0.5">
                  <span className="text-rose-500 line-through">
                    {JSON.stringify(d.old) ?? "null"}
                  </span>
                  <span className="text-emerald-500">
                    {JSON.stringify(d.new_)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <p className="text-[11px] text-emerald-600">
          No differences — current parser config produces identical results.
        </p>
      )}

      {/* Full new result */}
      <details className="text-[11px]">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
          Full re-parsed result
        </summary>
        <pre className="whitespace-pre-wrap rounded-sm bg-muted p-2 font-mono text-[10px] mt-1 max-h-48 overflow-y-auto">
          {JSON.stringify(newParsed, null, 2)}
        </pre>
      </details>
    </div>
  );
}

export function SignalDetailPanel({ log, open, onOpenChange }: Props) {
  const copy = useCopyToClipboard();
  const { data: rules } = useRoutingRules();
  const { user } = useAuth();
  const replayMutation = useReplaySignal();
  const [replayResult, setReplayResult] = useState<ReplayResponse | null>(null);

  if (!log) return null;

  const matchedRule = log.routing_rule_id && rules
    ? rules.find((r) => r.id === log.routing_rule_id) ?? null
    : null;

  const parsed = log.parsed_data;
  const symbol = parsed?.symbol as string | undefined;
  const direction = parsed?.direction as string | undefined;
  const action = (parsed?.action as string) || "entry";
  const entryPrice = parsed?.entry_price != null ? String(parsed.entry_price) : null;
  const stopLoss = parsed?.stop_loss != null ? String(parsed.stop_loss) : null;
  const takeProfits = parsed?.take_profits as number[] | undefined;
  const orderType = parsed?.order_type as string | undefined;
  const assetClass = parsed?.source_asset_class as string | undefined;
  const isFollow = action !== "entry";

  const steps = getPipelineSteps(log, matchedRule);

  const statusColor =
    log.status === "success" ? "text-emerald-500" :
    log.status === "failed" ? "text-rose-500" : "text-amber-500";

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[380px] sm:w-[420px] overflow-y-auto p-0">
        <SheetHeader className="p-4 pb-0">
          <SheetTitle className="text-sm font-medium flex items-center gap-2">
            {/* Direction arrow */}
            {direction && action === "entry" && (
              direction === "long" ? (
                <ArrowUp className="h-4 w-4 text-emerald-500" />
              ) : (
                <ArrowDown className="h-4 w-4 text-rose-500" />
              )
            )}
            {isFollow && <Reply className="h-4 w-4 text-muted-foreground" />}

            {/* Symbol chip */}
            {symbol && symbol !== "UNKNOWN" && (
              <span className="rounded bg-muted px-2 py-0.5 font-mono text-sm">
                {symbol}
              </span>
            )}

            {/* Action badge */}
            <span className="text-xs text-muted-foreground">
              {humanizeAction(action)}
            </span>

            {/* Status */}
            <span className={cn("text-xs font-medium ml-auto capitalize", statusColor)}>
              {log.status}
            </span>
          </SheetTitle>
          <p className="text-[11px] text-muted-foreground font-tabular">
            {new Date(log.processed_at).toLocaleString()}
          </p>
        </SheetHeader>

        <div className="p-4 space-y-4">
          {/* Error banner */}
          {log.error_message && log.status === "failed" && (
            <div className="rounded-md bg-rose-500/10 border border-rose-500/20 p-3">
              <p className="text-xs text-rose-600 dark:text-rose-400">{humanizeErrorMessage(log.error_message)}</p>
            </div>
          )}

          {/* Follow-up indicator */}
          {isFollow && (
            <div className="rounded-md bg-blue-500/10 border border-blue-500/20 p-3">
              <p className="text-xs text-blue-600 dark:text-blue-400">
                Follow-up: {humanizeAction(action)}{parsed?.percentage != null ? ` (${parsed.percentage}%)` : ""} — Symbol: {symbol}
              </p>
            </div>
          )}

          {/* Reply indicator */}
          {log.reply_to_msg_id && (
            <p className="text-[10px] text-muted-foreground">
              Reply to message #{log.reply_to_msg_id}
            </p>
          )}

          {/* Parsed Signal — structured fields */}
          {parsed && (
            <>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">Signal Analysis</p>
                <div className="grid grid-cols-3 gap-3">
                  <DataField label="Symbol" value={symbol} mono />
                  <DataField label="Direction" value={direction} />
                  <DataField label="Order" value={orderType} />
                </div>
                <div className="grid grid-cols-3 gap-3 mt-2">
                  <DataField label="Entry" value={entryPrice} mono />
                  <DataField label="Stop Loss" value={stopLoss} mono />
                  <DataField label="Asset" value={assetClass} />
                  {parsed?.percentage != null && (
                    <DataField label="Percentage" value={`${parsed.percentage}%`} />
                  )}
                  {parsed?.lots != null && (
                    <DataField label="Lots" value={String(parsed.lots)} mono />
                  )}
                </div>
                {takeProfits && takeProfits.length > 0 && (
                  <div className="mt-2">
                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      Take Profits
                    </span>
                    <div className="flex gap-2 mt-0.5">
                      {takeProfits.map((tp, i) => (
                        <span key={i} className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[11px] font-mono text-emerald-600 dark:text-emerald-400">
                          TP{i + 1}: {tp}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <Separator />
            </>
          )}

          {/* Route Attribution */}
          <div>
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">Route</p>
            {matchedRule ? (
              <div className="flex items-center gap-2">
                <Route className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="text-xs font-medium truncate">
                    {matchedRule.rule_name || matchedRule.source_channel_name || "Unnamed rule"}
                  </span>
                  <Badge variant="secondary" className="text-[9px] px-1.5 py-0 shrink-0">
                    {destinationTypeLabel(matchedRule.destination_type)}
                  </Badge>
                  <span className={cn(
                    "h-1.5 w-1.5 rounded-full shrink-0",
                    matchedRule.is_active ? "bg-emerald-500" : "bg-muted-foreground"
                  )} />
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                No rule evaluated — signal was filtered by Sage Intelligence
              </p>
            )}
          </div>

          <Separator />

          {/* Pipeline */}
          <div>
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">Pipeline</p>
            <div className="space-y-0">
              {steps.map((step, i) => (
                <div key={i} className="flex gap-2.5">
                  <div className="flex flex-col items-center">
                    {step.status === "done" ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                    ) : step.status === "failed" ? (
                      <XCircle className="h-3.5 w-3.5 text-rose-500 shrink-0" />
                    ) : (
                      <Circle className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    )}
                    {i < steps.length - 1 && (
                      <div className="w-px flex-1 bg-border min-h-[12px]" />
                    )}
                  </div>
                  <div className="pb-2.5">
                    <p className="text-[11px] font-medium leading-3.5">{step.label}</p>
                    <p className={cn(
                      "text-[10px] mt-0.5",
                      step.status === "failed" ? "text-rose-500" : "text-muted-foreground"
                    )}>
                      {step.detail}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <Separator />

          {/* Webhook Payload */}
          {log.webhook_payload && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  What Was Sent
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-5 px-1.5 text-[10px]"
                  onClick={() =>
                    copy(JSON.stringify(log.webhook_payload, null, 2), "Payload copied")
                  }
                >
                  <Copy className="mr-1 h-2.5 w-2.5" />
                  Copy
                </Button>
              </div>
              <pre className="whitespace-pre-wrap rounded-sm bg-muted p-2.5 font-mono text-[11px] max-h-48 overflow-y-auto leading-relaxed">
                {JSON.stringify(log.webhook_payload, null, 2)}
              </pre>
            </div>
          )}

          {/* Destination */}
          {matchedRule && (matchedRule.destination_label || matchedRule.destination_webhook_url) && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">Destination</p>
              {matchedRule.destination_label && (
                <p className="text-xs font-medium">{matchedRule.destination_label}</p>
              )}
              <p className="text-[10px] text-muted-foreground font-mono truncate mt-0.5">
                {matchedRule.destination_webhook_url}
              </p>
            </div>
          )}

          {/* Raw Message */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                Raw Message
              </p>
              <Button
                variant="ghost"
                size="sm"
                className="h-5 px-1.5 text-[10px]"
                onClick={() => copy(log.raw_message, "Message copied")}
              >
                <Copy className="mr-1 h-2.5 w-2.5" />
                Copy
              </Button>
            </div>
            <pre className="whitespace-pre-wrap rounded-sm bg-muted p-2.5 font-mono text-[11px] max-h-40 overflow-y-auto leading-relaxed text-muted-foreground">
              {log.raw_message}
            </pre>
          </div>

          {/* Ignored reason (if not already shown as error) */}
          {log.error_message && log.status === "ignored" && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Reason</p>
              <p className="text-xs text-amber-600 dark:text-amber-400">{humanizeErrorMessage(log.error_message)}</p>
            </div>
          )}

          {/* Signal Replay (admin only) */}
          {user?.is_admin && (
            <>
              <Separator />
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                    Re-parse with Current Config
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-6 px-2 text-[10px]"
                    disabled={replayMutation.isPending}
                    onClick={() => {
                      setReplayResult(null);
                      replayMutation.mutate(log.id, {
                        onSuccess: (data) => setReplayResult(data),
                      });
                    }}
                  >
                    {replayMutation.isPending ? (
                      <Loader2 className="mr-1 h-2.5 w-2.5 animate-spin" />
                    ) : (
                      <FlaskConical className="mr-1 h-2.5 w-2.5" />
                    )}
                    Re-parse
                  </Button>
                </div>
                {replayMutation.isError && (
                  <p className="text-[11px] text-rose-500">
                    {replayMutation.error instanceof Error
                      ? replayMutation.error.message
                      : "Re-parse failed"}
                  </p>
                )}
                {replayResult && <ReplayComparison replay={replayResult} />}
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
