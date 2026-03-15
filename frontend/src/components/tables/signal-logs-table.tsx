import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Reply } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/shared/status-badge";
import { SignalDetailPanel } from "@/components/shared/signal-detail-panel";
import { useRoutingRules } from "@/hooks/use-routing-rules";
import { truncateText } from "@/lib/utils";
import { cn } from "@/lib/utils";
import type { SignalLogResponse } from "@/types/api";

interface Props {
  logs: SignalLogResponse[];
}

function isFollowUp(log: SignalLogResponse): boolean {
  const action = log.parsed_data?.action as string | undefined;
  return !!action && action !== "entry";
}

function getSymbol(log: SignalLogResponse): string | null {
  return (log.parsed_data?.symbol as string) || null;
}

function getDirection(log: SignalLogResponse): string | null {
  return (log.parsed_data?.direction as string) || null;
}

function getAction(log: SignalLogResponse): string {
  return (log.parsed_data?.action as string) || "entry";
}

function getEntryPrice(log: SignalLogResponse): string | null {
  const price = log.parsed_data?.entry_price;
  return price != null ? String(price) : null;
}

const statusBorderColor: Record<string, string> = {
  success: "border-l-emerald-500",
  failed: "border-l-rose-500",
  ignored: "border-l-amber-500",
};

export function SignalLogsTable({ logs }: Props) {
  const [selectedLog, setSelectedLog] = useState<SignalLogResponse | null>(null);
  const { data: rules } = useRoutingRules();

  const ruleMap = useMemo(() => {
    const map = new Map<string, string>();
    if (rules) {
      for (const r of rules) {
        map.set(r.id, r.rule_name || r.source_channel_name || r.source_channel_id);
      }
    }
    return map;
  }, [rules]);

  return (
    <>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-20 text-[11px]">Time</TableHead>
              <TableHead className="hidden sm:table-cell w-10 text-[11px]" />
              <TableHead className="hidden md:table-cell w-28 text-[11px]">Symbol</TableHead>
              <TableHead className="hidden sm:table-cell w-24 text-[11px]">Route</TableHead>
              <TableHead className="text-[11px]">Signal</TableHead>
              <TableHead className="hidden md:table-cell w-20 text-[11px]">Price</TableHead>
              <TableHead className="w-20 text-[11px]">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {logs.map((log) => {
              const channelName = log.routing_rule_id
                ? ruleMap.get(log.routing_rule_id) ?? null
                : null;
              const symbol = getSymbol(log);
              const direction = getDirection(log);
              const action = getAction(log);
              const entryPrice = getEntryPrice(log);
              const borderColor = statusBorderColor[log.status] || "";

              return (
                <TableRow
                  key={log.id}
                  className={cn(
                    "cursor-pointer hover:bg-muted/40 border-l-2",
                    borderColor
                  )}
                  onClick={() => setSelectedLog(log)}
                >
                  <TableCell className="text-[11px] text-muted-foreground font-mono font-tabular py-2">
                    {new Date(log.processed_at).toLocaleTimeString("en-GB", {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell py-2">
                    {direction && action === "entry" ? (
                      direction === "long" ? (
                        <ArrowUp className="h-3.5 w-3.5 text-emerald-500" />
                      ) : (
                        <ArrowDown className="h-3.5 w-3.5 text-rose-500" />
                      )
                    ) : isFollowUp(log) ? (
                      <Reply className="h-3.5 w-3.5 text-muted-foreground" />
                    ) : null}
                  </TableCell>
                  <TableCell className="hidden md:table-cell py-2">
                    {symbol && symbol !== "UNKNOWN" ? (
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] font-mono font-medium">
                        {symbol}
                      </span>
                    ) : (
                      <span className="text-[11px] text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell text-[11px] text-muted-foreground py-2 truncate max-w-[120px]">
                    {channelName ?? "—"}
                  </TableCell>
                  <TableCell className="font-mono text-[11px] py-2">
                    <span className="inline-flex items-center gap-1">
                      <span className="sm:hidden">
                        {direction && action === "entry" ? (
                          direction === "long" ? (
                            <ArrowUp className="h-3 w-3 text-emerald-500 inline" />
                          ) : (
                            <ArrowDown className="h-3 w-3 text-rose-500 inline" />
                          )
                        ) : isFollowUp(log) ? (
                          <Reply className="h-3 w-3 text-muted-foreground inline" />
                        ) : null}
                      </span>
                      {truncateText(log.raw_message, 60)}
                    </span>
                    {channelName && (
                      <span className="block sm:hidden text-[10px] text-muted-foreground mt-0.5">
                        {channelName}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-[11px] font-mono font-tabular text-muted-foreground py-2">
                    {entryPrice ?? "—"}
                  </TableCell>
                  <TableCell className="py-2">
                    <StatusBadge
                      status={log.status as "success" | "failed" | "ignored"}
                    />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <SignalDetailPanel
        log={selectedLog}
        open={!!selectedLog}
        onOpenChange={(open) => {
          if (!open) setSelectedLog(null);
        }}
      />
    </>
  );
}
