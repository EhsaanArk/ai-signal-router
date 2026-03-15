import { useEffect, useState } from "react";
import { RefreshCw, ScrollText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState } from "@/components/shared/empty-state";
import { SignalLogsTable } from "@/components/tables/signal-logs-table";
import { useLogs } from "@/hooks/use-logs";
import { useRoutingRules } from "@/hooks/use-routing-rules";
import { useQueryClient } from "@tanstack/react-query";
import { usePageTitle } from "@/hooks/use-page-title";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;
const STATUS_OPTIONS = ["all", "success", "failed", "ignored"] as const;

const statusPillColors: Record<string, string> = {
  all: "",
  success: "data-[active=true]:bg-emerald-500/10 data-[active=true]:text-emerald-600 dark:data-[active=true]:text-emerald-400",
  failed: "data-[active=true]:bg-rose-500/10 data-[active=true]:text-rose-600 dark:data-[active=true]:text-rose-400",
  ignored: "data-[active=true]:bg-amber-500/10 data-[active=true]:text-amber-600 dark:data-[active=true]:text-amber-400",
};

export function LogsPage() {
  usePageTitle("Signal Logs");
  const [offset, setOffset] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [ruleFilter, setRuleFilter] = useState<string>("all");
  const [live, setLive] = useState(false);
  const queryClient = useQueryClient();
  const { data: rules } = useRoutingRules();
  const { data, isLoading, isFetching, isError, error } = useLogs(
    PAGE_SIZE,
    offset,
    statusFilter,
    ruleFilter !== "all" ? ruleFilter : undefined,
  );

  // Auto-refresh when live mode is on
  useEffect(() => {
    if (!live) return;
    const interval = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ["logs"] });
    }, 10_000);
    return () => clearInterval(interval);
  }, [live, queryClient]);

  const hasMore = data ? offset + PAGE_SIZE < data.total : false;

  function handleStatusChange(status: string) {
    setStatusFilter(status);
    setOffset(0);
  }

  function handleRuleChange(value: string) {
    setRuleFilter(value);
    setOffset(0);
  }

  return (
    <div className="space-y-4">
      {/* Header + Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Status pills */}
          <div className="flex gap-1">
            {STATUS_OPTIONS.map((status) => (
              <button
                key={status}
                data-active={statusFilter === status}
                onClick={() => handleStatusChange(status)}
                className={cn(
                  "rounded-sm px-2.5 py-1 text-[11px] font-medium transition-colors",
                  "text-muted-foreground hover:text-foreground hover:bg-muted",
                  "data-[active=true]:bg-primary/10 data-[active=true]:text-primary",
                  statusPillColors[status]
                )}
              >
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </button>
            ))}
          </div>

          {/* Route filter */}
          {rules && rules.length > 0 && (
            <Select value={ruleFilter} onValueChange={handleRuleChange}>
              <SelectTrigger className="w-[180px] h-7 text-[11px]">
                <SelectValue placeholder="All routes" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All routes</SelectItem>
                {rules.map((rule) => (
                  <SelectItem key={rule.id} value={rule.id}>
                    {rule.rule_name || rule.destination_label || rule.source_channel_name || rule.source_channel_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        <div className="flex items-center gap-1">
          {/* Live toggle */}
          <button
            onClick={() => setLive(!live)}
            className={cn(
              "flex items-center gap-1.5 rounded-sm px-2 py-1 text-[11px] font-medium transition-colors",
              live
                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            )}
          >
            <span className={cn(
              "h-1.5 w-1.5 rounded-full",
              live ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground"
            )} />
            Live
          </button>

          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => queryClient.invalidateQueries({ queryKey: ["logs"] })}
            aria-label="Refresh logs"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-1">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      ) : isError ? (
        <EmptyState
          icon={ScrollText}
          title="Failed to load logs"
          description={error instanceof Error ? error.message : "An unexpected error occurred."}
          actionLabel="Retry"
          onAction={() => queryClient.invalidateQueries({ queryKey: ["logs"] })}
        />
      ) : !data?.items.length ? (
        <EmptyState
          icon={ScrollText}
          title="No signal logs"
          description={
            statusFilter !== "all"
              ? `No ${statusFilter} signals found.`
              : "Signal logs will appear here once your routes start processing signals. Set up a route first if you haven't already."
          }
          actionLabel={statusFilter === "all" ? "Set Up Routes" : undefined}
          onAction={statusFilter === "all" ? () => window.location.assign("/routing-rules") : undefined}
        />
      ) : (
        <>
          <div className={isFetching && !live ? "opacity-50 pointer-events-none" : ""}>
            <SignalLogsTable logs={data.items} />
          </div>
          <div className="flex items-center justify-between">
            <p className="text-[11px] text-muted-foreground font-tabular">
              {offset + 1}–{Math.min(offset + PAGE_SIZE, data.total)} of {data.total}
            </p>
            <div className="flex gap-1">
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                disabled={offset === 0 || isFetching}
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                disabled={!hasMore || isFetching}
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
