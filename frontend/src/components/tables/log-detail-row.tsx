import { CheckCircle2, Circle, Copy, XCircle } from "lucide-react";
import { TableCell, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { useCopyToClipboard } from "@/hooks/use-clipboard";
import { useRoutingRules } from "@/hooks/use-routing-rules";
import type { SignalLogResponse } from "@/types/api";

interface Props {
  log: SignalLogResponse;
  colSpan?: number;
}

function isFollowUp(log: SignalLogResponse): boolean {
  const action = log.parsed_data?.action as string | undefined;
  return !!action && action !== "entry";
}

function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

interface PipelineStep {
  label: string;
  detail: string;
  status: "done" | "failed" | "skipped";
}

function getPipelineSteps(log: SignalLogResponse, channelName: string | null): PipelineStep[] {
  const steps: PipelineStep[] = [];

  // Step 1: Telegram received
  steps.push({
    label: "Telegram Signal Received",
    detail: channelName
      ? `From: ${channelName}`
      : log.channel_id
        ? `Channel: ${log.channel_id}`
        : "Source channel",
    status: "done",
  });

  // Step 2: Parsed
  if (log.status === "ignored") {
    steps.push({
      label: "Signal Parsed",
      detail: "Signal was ignored (not a valid trading signal)",
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

  // Step 3: Webhook dispatched
  if (log.webhook_payload) {
    steps.push({
      label: "Webhook Dispatched",
      detail: "Payload sent to destination",
      status: "done",
    });
  }

  // Step 4: Result
  steps.push({
    label: log.status === "success" ? "Routed Successfully" : "Routing Failed",
    detail: log.status === "success"
      ? `Completed at ${formatTimestamp(log.processed_at)}`
      : log.error_message || "Unknown error",
    status: log.status === "success" ? "done" : "failed",
  });

  return steps;
}

export function LogDetailRow({ log, colSpan = 3 }: Props) {
  const copy = useCopyToClipboard();
  const { data: rules } = useRoutingRules();

  const matchedRule = log.routing_rule_id && rules
    ? rules.find((r) => r.id === log.routing_rule_id) ?? null
    : null;
  const channelName = matchedRule?.rule_name || matchedRule?.source_channel_name || null;

  const steps = getPipelineSteps(log, channelName);

  return (
    <TableRow>
      <TableCell colSpan={colSpan} className="bg-muted/50 p-4">
        <div className="space-y-4 text-sm">
          {isFollowUp(log) && (
            <div className="rounded border border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950 p-2">
              <p className="font-medium text-xs text-blue-700 dark:text-blue-300 mb-1">
                Reply to Original Signal
              </p>
              <p className="text-xs text-blue-600 dark:text-blue-400">
                Action: {log.parsed_data?.action as string} — Symbol inherited: {log.parsed_data?.symbol as string}
              </p>
            </div>
          )}

          {/* Pipeline Timeline */}
          <div>
            <p className="font-medium text-xs text-muted-foreground mb-2">
              Signal Pipeline
            </p>
            <div className="space-y-0">
              {steps.map((step, i) => (
                <div key={i} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    {step.status === "done" ? (
                      <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
                    ) : step.status === "failed" ? (
                      <XCircle className="h-4 w-4 text-red-500 shrink-0" />
                    ) : (
                      <Circle className="h-4 w-4 text-muted-foreground shrink-0" />
                    )}
                    {i < steps.length - 1 && (
                      <div className="w-px flex-1 bg-border min-h-[16px]" />
                    )}
                  </div>
                  <div className="pb-3">
                    <p className="text-xs font-medium leading-4">{step.label}</p>
                    <p className={`text-xs ${step.status === "failed" ? "text-destructive" : "text-muted-foreground"}`}>
                      {step.detail}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <p className="font-medium text-xs text-muted-foreground">
                Raw Message
              </p>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs"
                onClick={() => copy(log.raw_message, "Raw message copied")}
              >
                <Copy className="mr-1 h-3 w-3" />
                Copy
              </Button>
            </div>
            <pre className="whitespace-pre-wrap rounded bg-muted p-2 font-mono text-xs max-h-60 overflow-y-auto">
              {log.raw_message}
            </pre>
          </div>

          {log.parsed_data && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="font-medium text-xs text-muted-foreground">
                  Signal Analysis
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs"
                  onClick={() =>
                    copy(
                      JSON.stringify(log.parsed_data, null, 2),
                      "Parsed data copied"
                    )
                  }
                >
                  <Copy className="mr-1 h-3 w-3" />
                  Copy
                </Button>
              </div>
              <pre className="whitespace-pre-wrap rounded bg-muted p-2 font-mono text-xs max-h-60 overflow-y-auto">
                {JSON.stringify(log.parsed_data, null, 2)}
              </pre>
            </div>
          )}

          {log.webhook_payload && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="font-medium text-xs text-muted-foreground">
                  What Was Sent
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs"
                  onClick={() =>
                    copy(
                      JSON.stringify(log.webhook_payload, null, 2),
                      "Webhook payload copied"
                    )
                  }
                >
                  <Copy className="mr-1 h-3 w-3" />
                  Copy
                </Button>
              </div>
              <pre className="whitespace-pre-wrap rounded bg-muted p-2 font-mono text-xs max-h-60 overflow-y-auto">
                {JSON.stringify(log.webhook_payload, null, 2)}
              </pre>
            </div>
          )}

          {matchedRule && (matchedRule.destination_label || matchedRule.destination_webhook_url) && (
            <div>
              <p className="font-medium text-xs text-muted-foreground mb-1">
                Destination
              </p>
              {matchedRule.destination_label && (
                <p className="text-xs font-medium">{matchedRule.destination_label}</p>
              )}
              <p className="text-[11px] text-muted-foreground font-mono truncate">
                {matchedRule.destination_webhook_url}
              </p>
            </div>
          )}

          {log.error_message && (
            <div>
              <p className="font-medium text-xs text-muted-foreground mb-1">
                Error
              </p>
              <p className="text-destructive text-xs">{log.error_message}</p>
            </div>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}
