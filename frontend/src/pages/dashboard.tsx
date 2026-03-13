import { Link } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/shared/status-badge";
import { useTelegramStatus } from "@/hooks/use-telegram";
import { useRoutingRules } from "@/hooks/use-routing-rules";
import { useRecentLogs } from "@/hooks/use-logs";
import { useAuth } from "@/contexts/auth-context";
import { getTierLimit } from "@/lib/tier";
import { formatRelativeTime, truncateText } from "@/lib/utils";
import { usePageTitle } from "@/hooks/use-page-title";

export function DashboardPage() {
  usePageTitle("Dashboard");
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { data: telegramStatus, isLoading: tgLoading, isError: tgError, isFetching: tgFetching } = useTelegramStatus();
  const { data: rules, isLoading: rulesLoading, isError: rulesError, isFetching: rulesFetching } = useRoutingRules();
  const { data: logsData, isLoading: logsLoading, isError: logsError, isFetching: logsFetching } = useRecentLogs(5);

  const anyFetching = tgFetching || rulesFetching || logsFetching;

  function handleRefresh() {
    queryClient.invalidateQueries({ queryKey: ["telegram-status"] });
    queryClient.invalidateQueries({ queryKey: ["routing-rules"] });
    queryClient.invalidateQueries({ queryKey: ["logs"] });
  }

  const tier = user?.subscription_tier || "free";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleRefresh}
          aria-label="Refresh dashboard"
        >
          <RefreshCw className={`h-4 w-4 ${anyFetching ? "animate-spin" : ""}`} />
        </Button>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {/* Telegram Status */}
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Telegram</CardDescription>
            <CardTitle className="text-lg">Connection Status</CardTitle>
          </CardHeader>
          <CardContent>
            {tgLoading ? (
              <Skeleton className="h-6 w-24" />
            ) : tgError ? (
              <p className="text-sm text-destructive">Failed to load</p>
            ) : (
              <Link to="/telegram">
                <StatusBadge
                  status={
                    telegramStatus?.connected ? "connected" : "disconnected"
                  }
                />
              </Link>
            )}
          </CardContent>
        </Card>

        {/* Routing Rules */}
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Routing Rules</CardDescription>
            <CardTitle className="text-lg">Active Rules</CardTitle>
          </CardHeader>
          <CardContent>
            {rulesLoading ? (
              <Skeleton className="h-6 w-16" />
            ) : rulesError ? (
              <p className="text-sm text-destructive">Failed to load</p>
            ) : (
              <Link
                to="/routing-rules"
                className="text-2xl font-bold hover:underline"
              >
                {rules?.filter((r) => r.is_active).length ?? 0}
                <span className="text-sm font-normal text-muted-foreground">
                  {" "}
                  / {getTierLimit(tier)}
                </span>
              </Link>
            )}
          </CardContent>
        </Card>

        {/* Recent Signals */}
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Signal Logs</CardDescription>
            <CardTitle className="text-lg">Recent Signals</CardTitle>
          </CardHeader>
          <CardContent>
            {logsLoading ? (
              <Skeleton className="h-6 w-16" />
            ) : logsError ? (
              <p className="text-sm text-destructive">Failed to load</p>
            ) : (
              <Link
                to="/logs"
                className="text-2xl font-bold hover:underline"
              >
                {logsData?.total ?? 0}
                <span className="text-sm font-normal text-muted-foreground">
                  {" "}
                  total
                </span>
              </Link>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Logs List */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Recent Signals</CardTitle>
        </CardHeader>
        <CardContent>
          {logsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !logsData?.items.length ? (
            <p className="text-sm text-muted-foreground">
              No signals processed yet.
            </p>
          ) : (
            <div className="space-y-2">
              {logsData.items.map((log) => (
                <div
                  key={log.id}
                  className="flex items-center justify-between rounded-md border p-3 text-sm"
                >
                  <div className="flex-1 truncate">
                    {truncateText(log.raw_message, 60)}
                  </div>
                  <div className="flex items-center gap-3">
                    <StatusBadge
                      status={
                        log.status as "success" | "failed" | "ignored"
                      }
                    />
                    <span className="text-xs text-muted-foreground">
                      {formatRelativeTime(log.processed_at)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
