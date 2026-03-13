import { useState } from "react";
import { RefreshCw, ScrollText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { SignalLogsTable } from "@/components/tables/signal-logs-table";
import { useLogs } from "@/hooks/use-logs";
import { useQueryClient } from "@tanstack/react-query";
import { usePageTitle } from "@/hooks/use-page-title";

const PAGE_SIZE = 20;
const STATUS_OPTIONS = ["all", "success", "failed", "ignored"] as const;

export function LogsPage() {
  usePageTitle("Signal Logs");
  const [offset, setOffset] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const queryClient = useQueryClient();
  const { data, isLoading, isFetching } = useLogs(PAGE_SIZE, offset, statusFilter);

  const hasMore = data ? offset + PAGE_SIZE < data.total : false;

  function handleStatusChange(status: string) {
    setStatusFilter(status);
    setOffset(0);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Signal Logs</h1>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => queryClient.invalidateQueries({ queryKey: ["logs"] })}
          aria-label="Refresh logs"
        >
          <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {/* Status filter */}
      <div className="flex gap-2">
        {STATUS_OPTIONS.map((status) => (
          <Button
            key={status}
            variant={statusFilter === status ? "default" : "outline"}
            size="sm"
            onClick={() => handleStatusChange(status)}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </Button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : !data?.items.length ? (
        <EmptyState
          icon={ScrollText}
          title="No signal logs"
          description={
            statusFilter !== "all"
              ? `No ${statusFilter} signals found.`
              : "Signal logs will appear here once your routing rules start processing signals."
          }
        />
      ) : (
        <>
          <div className={isFetching ? "opacity-50 pointer-events-none" : ""}>
            <SignalLogsTable logs={data.items} />
          </div>
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Showing {offset + 1}-{Math.min(offset + PAGE_SIZE, data.total)}{" "}
              of {data.total}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0 || isFetching}
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
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
