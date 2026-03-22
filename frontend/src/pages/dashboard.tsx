import { Link, Navigate, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  CheckCircle2,
  Plus,
  Radio,
  RefreshCw,
  Reply,
  WifiOff,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useTelegramStatus } from "@/hooks/use-telegram";
import { useRoutingRules } from "@/hooks/use-routing-rules";
import { useRecentLogs, useLogStats } from "@/hooks/use-logs";
import { useAuth } from "@/contexts/auth-context";
import { getTierLimit } from "@/lib/tier";
import { formatRelativeTime, humanizeAction, truncateText } from "@/lib/utils";
import { usePageTitle } from "@/hooks/use-page-title";
import { cn } from "@/lib/utils";
import type { SignalLogResponse } from "@/types/api";

function isFollowUp(log: SignalLogResponse): boolean {
  const action = log.parsed_data?.action as string | undefined;
  return !!action && action !== "entry";
}

function getLogSymbol(log: SignalLogResponse): string | null {
  return (log.parsed_data?.symbol as string) || null;
}

function getLogDirection(log: SignalLogResponse): string | null {
  return (log.parsed_data?.direction as string) || null;
}

function getLogAction(log: SignalLogResponse): string {
  return (log.parsed_data?.action as string) || "entry";
}

export function DashboardPage() {
  usePageTitle("Dashboard");
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: telegramStatus, isLoading: tgLoading, isFetching: tgFetching } = useTelegramStatus();
  const { data: rules, isLoading: rulesLoading, isFetching: rulesFetching } = useRoutingRules();
  const { data: logsData, isLoading: logsLoading, isFetching: logsFetching } = useRecentLogs(10);
  const { data: logStats } = useLogStats();

  // Redirect new users to setup wizard
  const setupComplete = localStorage.getItem("sgm_setup_complete") === "true";
  if (!setupComplete && !rulesLoading && (rules?.length ?? 0) === 0) {
    return <Navigate to="/setup" replace />;
  }

  const anyFetching = tgFetching || rulesFetching || logsFetching;
  const isConnected = telegramStatus?.connected ?? false;

  const tier = user?.subscription_tier || "free";
  const successRate = logStats && logStats.total > 0
    ? ((logStats.success / logStats.total) * 100).toFixed(1)
    : null;

  function handleRefresh() {
    queryClient.invalidateQueries({ queryKey: ["telegram-status"] });
    queryClient.invalidateQueries({ queryKey: ["routing-rules"] });
    queryClient.invalidateQueries({ queryKey: ["logs"] });
  }

  return (
    <div className="space-y-4">
      {/* Stats Strip */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          {/* Telegram Pipeline Heartbeat */}
          <Link to="/telegram" className="flex items-center gap-2 group" title={
            tgLoading ? "Loading..." :
            isConnected
              ? `Connected${telegramStatus?.last_signal_at ? ` · Last signal: ${formatRelativeTime(telegramStatus.last_signal_at)}` : ""}`
              : `Disconnected${telegramStatus?.disconnected_reason ? ` (${telegramStatus.disconnected_reason})` : ""}`
          }>
            <span className={cn(
              "h-2 w-2 rounded-full",
              isConnected ? "bg-emerald-500" :
              telegramStatus?.disconnected_reason === "flood_wait_exhausted"
                ? "bg-amber-500 animate-pulse"
                : "bg-rose-500 animate-pulse"
            )} />
            <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">
              {tgLoading ? "..." :
               isConnected ? "Connected" :
               telegramStatus?.disconnected_reason === "flood_wait_exhausted" ? "Reconnecting" :
               "Disconnected"}
            </span>
            {isConnected && telegramStatus?.last_signal_at && (
              <span className="hidden sm:inline text-[10px] text-muted-foreground/60">
                · {formatRelativeTime(telegramStatus.last_signal_at)}
              </span>
            )}
          </Link>

          {/* Rules */}
          <Link to="/routing-rules" className="flex items-center gap-1.5 group">
            <span className="text-sm font-semibold font-tabular">
              {rulesLoading ? "—" : rules?.filter((r) => r.is_active).length ?? 0}
            </span>
            <span className="text-xs text-muted-foreground font-tabular">
              / {getTierLimit(tier)}
            </span>
            <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">
              routes
            </span>
          </Link>

          {/* Signals */}
          <Link to="/logs" className="flex items-center gap-1.5 group">
            <span className="text-sm font-semibold font-tabular">
              {logsLoading ? "—" : logsData?.total ?? 0}
            </span>
            <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">
              signals
            </span>
            {logStats && logStats.total > 0 && (
              <span className="flex items-center gap-1 ml-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                <span className="text-[10px] text-muted-foreground font-tabular">{logStats.success}</span>
                <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
                <span className="text-[10px] text-muted-foreground font-tabular">{logStats.failed}</span>
                <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                <span className="text-[10px] text-muted-foreground font-tabular">{logStats.ignored}</span>
              </span>
            )}
          </Link>

          {/* Success Rate */}
          {successRate !== null && (
            <span className="hidden md:flex items-center gap-1.5">
              <span className={cn(
                "text-sm font-semibold font-tabular",
                parseFloat(successRate) >= 90 ? "text-emerald-500" :
                parseFloat(successRate) >= 70 ? "text-amber-500" : "text-rose-500"
              )}>
                {successRate}%
              </span>
              <span className="text-xs text-muted-foreground">success</span>
            </span>
          )}
        </div>

        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={handleRefresh}
          aria-label="Refresh dashboard"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", anyFetching && "animate-spin")} />
        </Button>
      </div>

      {/* Telegram disconnected banner */}
      {!tgLoading && !isConnected && (rules?.length ?? 0) > 0 && (
        <div className="flex items-center gap-2 bg-rose-500/10 border border-rose-500/20 rounded-md px-3 py-2">
          <WifiOff className="h-3.5 w-3.5 text-rose-500 shrink-0" />
          <p className="text-xs text-rose-600 dark:text-rose-400 flex-1">
            Telegram is disconnected. Signal routing is paused.
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-[11px] text-rose-600 hover:text-rose-700 dark:text-rose-400"
            onClick={() => navigate("/telegram")}
          >
            Reconnect
            <ArrowRight className="ml-1 h-3 w-3" />
          </Button>
        </div>
      )}

      {/* Empty state for users with no routes */}
      {!rulesLoading && (rules?.length ?? 0) === 0 && (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center py-10 space-y-3">
            <p className="text-sm font-medium">Create your first signal route to get started</p>
            <p className="text-xs text-muted-foreground text-center max-w-sm">
              Connect a Telegram channel to a SageMaster webhook and start routing trading signals automatically.
            </p>
            <Button
              size="sm"
              onClick={() => navigate(isConnected ? "/routing-rules/new" : "/telegram")}
            >
              {isConnected ? "Create Route" : "Connect Telegram & Create Route"}
              <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Waiting for first signal — setup complete but no signals yet */}
      {setupComplete && !rulesLoading && (rules?.length ?? 0) > 0 && !logsLoading && (logStats?.total ?? 0) === 0 && (
        <Card className="border-primary/20 bg-primary/[0.02]">
          <CardContent className="py-8 space-y-4">
            <div className="flex flex-col items-center text-center space-y-2">
              <span className="relative flex h-8 w-8 items-center justify-center">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/20" />
                <Radio className="relative h-5 w-5 text-primary" />
              </span>
              <p className="text-sm font-medium">Listening for signals...</p>
              <p className="text-xs text-muted-foreground max-w-xs">
                Your routes are active. When a trading signal is posted in your Telegram channel, it will appear here automatically.
              </p>
            </div>
            <div className="flex flex-col items-center gap-1.5">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                Telegram connected
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                {rules?.length} route{(rules?.length ?? 0) !== 1 ? "s" : ""} active
              </div>
            </div>
            <p className="text-[10px] text-muted-foreground text-center">
              Tip: Send a test message in your Telegram channel to verify the connection.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Routes Overview */}
      {rules && rules.length > 0 && (
        <Card>
          <CardHeader className="pb-2 pt-4 px-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">Routes Overview</CardTitle>
              {(rules?.length ?? 0) < getTierLimit(tier) && (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-6 text-[11px]"
                  onClick={() => navigate("/routing-rules/new")}
                >
                  <Plus className="mr-1 h-3 w-3" />
                  Create Route
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            <div className="space-y-1.5">
              {rules.map((rule) => {
                const ruleLogs = logsData?.items.filter(
                  (l) => l.routing_rule_id === rule.id
                ) ?? [];
                const successCount = ruleLogs.filter((l) => l.status === "success").length;
                const failCount = ruleLogs.filter((l) => l.status === "failed").length;
                const lastLog = ruleLogs[0];

                return (
                  <div
                    key={rule.id}
                    className={cn(
                      "flex items-center gap-3 rounded-md border px-3 py-2 border-l-2",
                      rule.is_active ? "border-l-emerald-500" : "border-l-zinc-400"
                    )}
                  >
                    <span className={cn(
                      "h-1.5 w-1.5 rounded-full shrink-0",
                      rule.is_active ? "bg-emerald-500" : "bg-zinc-400"
                    )} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate">
                        {rule.rule_name || rule.source_channel_name || rule.source_channel_id}
                      </p>
                      <p className="text-[10px] text-muted-foreground truncate">
                        {rule.destination_label || "Webhook"}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      {ruleLogs.length > 0 && (
                        <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                          <span className="h-1 w-1 rounded-full bg-emerald-500" />
                          {successCount}
                          <span className="h-1 w-1 rounded-full bg-rose-500 ml-1" />
                          {failCount}
                        </span>
                      )}
                      {lastLog && (
                        <span className="text-[10px] text-muted-foreground">
                          {formatRelativeTime(lastLog.processed_at)}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Failures */}
      {logsData && logsData.items.some((l) => l.status === "failed") && (
        <Card className="border-rose-500/20">
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="text-sm font-medium flex items-center gap-2 text-rose-600 dark:text-rose-400">
              <AlertTriangle className="h-3.5 w-3.5" />
              Recent Failures
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            <div className="space-y-1">
              {logsData.items
                .filter((l) => l.status === "failed")
                .slice(0, 3)
                .map((log) => {
                  const ruleName = log.routing_rule_id
                    ? (rules?.find((r) => r.id === log.routing_rule_id)?.rule_name
                      || rules?.find((r) => r.id === log.routing_rule_id)?.source_channel_name
                      || null)
                    : null;
                  return (
                    <div key={log.id} className="flex items-center gap-2 text-xs">
                      <span className="h-1.5 w-1.5 rounded-full bg-rose-500 shrink-0" />
                      <span className="font-medium truncate flex-1">
                        {ruleName || "Unknown route"}
                      </span>
                      <span className="text-[10px] text-muted-foreground truncate max-w-[200px]">
                        {log.error_message || "Failed"}
                      </span>
                      <span className="text-[10px] text-muted-foreground shrink-0">
                        {formatRelativeTime(log.processed_at)}
                      </span>
                    </div>
                  );
                })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Signals — compact trading-style table */}
      <Card>
        <CardHeader className="pb-2 pt-4 px-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium">Recent Signals</CardTitle>
            <Link to="/logs" className="text-xs text-primary hover:underline">
              View all
            </Link>
          </div>
        </CardHeader>
        <CardContent className="px-0 pb-2">
          {logsLoading ? (
            <div className="space-y-1 px-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : !logsData?.items.length ? (
            <p className="text-xs text-muted-foreground px-4 py-6 text-center">
              No signals processed yet
            </p>
          ) : (
            <div className="divide-y divide-border">
              {logsData.items.map((log) => {
                const symbol = getLogSymbol(log);
                const direction = getLogDirection(log);
                const action = getLogAction(log);
                const statusColor =
                  log.status === "success" ? "bg-emerald-500" :
                  log.status === "failed" ? "bg-rose-500" : "bg-amber-500";

                return (
                  <div
                    key={log.id}
                    className="flex items-center gap-3 px-4 py-2 text-xs hover:bg-muted/30 transition-colors"
                  >
                    {/* Status dot */}
                    <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", statusColor)} />

                    {/* Time */}
                    <span className="text-[11px] text-muted-foreground font-mono font-tabular w-12 shrink-0">
                      {new Date(log.processed_at).toLocaleTimeString("en-GB", {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })}
                    </span>

                    {/* Direction arrow */}
                    {direction && action === "entry" && (
                      direction === "long" ? (
                        <ArrowUp className="h-3 w-3 text-emerald-500 shrink-0" />
                      ) : (
                        <ArrowDown className="h-3 w-3 text-rose-500 shrink-0" />
                      )
                    )}
                    {isFollowUp(log) && (
                      <Reply className="h-3 w-3 text-muted-foreground shrink-0" />
                    )}

                    {/* Symbol chip */}
                    {symbol && symbol !== "UNKNOWN" && (
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] font-mono font-medium shrink-0">
                        {symbol}
                      </span>
                    )}

                    {/* Action */}
                    {action !== "entry" && (
                      <span className="text-[11px] text-muted-foreground shrink-0">
                        {humanizeAction(action)}
                      </span>
                    )}

                    {/* Message (truncated, fills remaining space) */}
                    <span className="flex-1 truncate text-muted-foreground">
                      {truncateText(log.raw_message, 50)}
                    </span>

                    {/* Relative time */}
                    <span className="text-[10px] text-muted-foreground shrink-0">
                      {formatRelativeTime(log.processed_at)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default DashboardPage;
