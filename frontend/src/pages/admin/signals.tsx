import { useState } from "react";
import { Activity } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/shared/status-badge";
import { SignalDetailPanel } from "@/components/shared/signal-detail-panel";
import { useAdminSignals, useAdminSignalStats } from "@/hooks/use-admin";
import { usePageTitle } from "@/hooks/use-page-title";
import { cn } from "@/lib/utils";
import type { AdminSignalLog } from "@/types/api";

const PAGE_SIZE = 50;
const STATUS_FILTERS = ["all", "success", "failed", "ignored"];

export function AdminSignalsPage() {
  usePageTitle("Admin - All Signals");
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState("all");
  const [userEmail, setUserEmail] = useState("");
  const [channelId, setChannelId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [selectedSignal, setSelectedSignal] = useState<AdminSignalLog | null>(null);

  const { data: stats } = useAdminSignalStats();
  const { data, isLoading } = useAdminSignals(PAGE_SIZE, page * PAGE_SIZE, {
    status: statusFilter,
    user_email: userEmail || undefined,
    channel_id: channelId || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-medium">All Signals</h2>

      {/* Stats banner */}
      {stats && (
        <div className="flex items-center gap-4 rounded-md border px-3 py-2 text-xs">
          <div className="flex items-center gap-1.5">
            <Activity className="h-3 w-3 text-muted-foreground" />
            <span className="font-tabular font-medium">{stats.total_today}</span>
            <span className="text-muted-foreground">today</span>
          </div>
          <span className="text-border">|</span>
          <div>
            <span className={cn(
              "font-tabular font-medium",
              stats.success_rate_24h >= 90 ? "text-emerald-500" : stats.success_rate_24h >= 70 ? "text-amber-500" : "text-rose-500",
            )}>
              {stats.success_rate_24h}%
            </span>
            <span className="text-muted-foreground ml-1">success (24h)</span>
          </div>
          {stats.top_failing_channels.length > 0 && (
            <>
              <span className="text-border">|</span>
              <div className="text-muted-foreground">
                Top failing:{" "}
                {stats.top_failing_channels.slice(0, 3).map((ch, i) => (
                  <span key={ch.channel_id}>
                    {i > 0 && ", "}
                    <span className="font-mono text-foreground">{ch.channel_id}</span>
                    <span className="text-rose-500 ml-0.5">({ch.fail_count})</span>
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* Status filter pills */}
      <div className="flex items-center gap-1.5">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => { setStatusFilter(s); setPage(0); }}
            className={cn(
              "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              statusFilter === s
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:text-foreground",
            )}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {/* Filter row */}
      <div className="flex gap-2 flex-wrap">
        <Input
          placeholder="User email..."
          value={userEmail}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => { setUserEmail(e.target.value); setPage(0); }}
          className="h-8 text-xs w-40"
        />
        <Input
          placeholder="Channel ID..."
          value={channelId}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => { setChannelId(e.target.value); setPage(0); }}
          className="h-8 text-xs w-40 font-mono"
        />
        <Input
          type="date"
          value={dateFrom}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => { setDateFrom(e.target.value); setPage(0); }}
          className="h-8 text-xs w-36"
          placeholder="From"
        />
        <Input
          type="date"
          value={dateTo}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => { setDateTo(e.target.value); setPage(0); }}
          className="h-8 text-xs w-36"
          placeholder="To"
        />
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-[10px] w-16">Status</TableHead>
              <TableHead className="text-[10px]">Time</TableHead>
              <TableHead className="text-[10px]">User</TableHead>
              <TableHead className="text-[10px]">Channel</TableHead>
              <TableHead className="text-[10px]">Message</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 5 }).map((_, j) => (
                    <TableCell key={j}><div className="h-4 w-16 bg-muted animate-pulse rounded" /></TableCell>
                  ))}
                </TableRow>
              ))
            ) : data?.items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-xs text-muted-foreground py-8">
                  No signals found
                </TableCell>
              </TableRow>
            ) : (
              data?.items.map((sig) => (
                <TableRow
                  key={sig.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => setSelectedSignal(sig)}
                >
                  <TableCell>
                    <StatusBadge status={sig.status as "success" | "failed" | "ignored"} />
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                    {new Date(sig.processed_at).toLocaleString("en-US", {
                      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                    })}
                  </TableCell>
                  <TableCell className="text-xs">{sig.user_email}</TableCell>
                  <TableCell className="text-xs font-mono">{sig.channel_id || "—"}</TableCell>
                  <TableCell className="text-xs max-w-[250px] truncate">{sig.raw_message}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            {data?.total} signals | Page {page + 1} of {totalPages}
          </p>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" className="h-7 text-xs" disabled={page === 0} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <Button variant="outline" size="sm" className="h-7 text-xs" disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Signal detail panel */}
      {selectedSignal && (
        <SignalDetailPanel
          log={selectedSignal}
          open={!!selectedSignal}
          onOpenChange={(open) => { if (!open) setSelectedSignal(null); }}
        />
      )}
    </div>
  );
}
