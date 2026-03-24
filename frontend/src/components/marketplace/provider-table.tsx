import { BadgeCheck } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { MarketplaceProvider } from "@/types/marketplace";
import { fmtPips, ASSET_SHORT } from "./format";

interface ProviderTableProps {
  providers: MarketplaceProvider[];
  subscribedIds: Set<string>;
  onSubscribe: (provider: MarketplaceProvider) => void;
  onUnsubscribe: (providerId: string) => void;
}

export function ProviderTable({
  providers,
  subscribedIds,
  onSubscribe,
  onUnsubscribe,
}: ProviderTableProps) {
  return (
    <div className="rounded-md border border-border/40">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent border-border/40">
            <TableHead className="w-[220px] text-[11px] font-medium">Provider</TableHead>
            <TableHead className="w-[60px] text-[11px] font-medium text-center">Type</TableHead>
            <TableHead className="w-[80px] text-[11px] font-medium text-right">Win Rate</TableHead>
            <TableHead className="w-[100px] text-[11px] font-medium text-right">P&L (pips)</TableHead>
            <TableHead className="w-[80px] text-[11px] font-medium text-right">Max DD</TableHead>
            <TableHead className="w-[60px] text-[11px] font-medium text-right">Signals</TableHead>
            <TableHead className="w-[70px] text-[11px] font-medium text-right">Followers</TableHead>
            <TableHead className="w-[60px] text-[11px] font-medium text-right">Track</TableHead>
            <TableHead className="w-[80px] text-[11px] font-medium text-right"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {providers.map((p) => {
            const isFollowing = subscribedIds.has(p.id);
            const wr = p.win_rate;
            const hasData = wr !== null;

            return (
              <TableRow
                key={p.id}
                role="article"
                aria-label={`${p.name} - ${hasData ? `${wr!.toFixed(1)}%` : "N/A"} win rate`}
                className="border-border/30 hover:bg-accent/5 transition-colors"
              >
                {/* Provider name */}
                <TableCell className="py-2.5">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-medium truncate max-w-[180px]">
                      {p.name}
                    </span>
                    {p.track_record_days >= 30 && p.signal_count >= 20 && (
                      <BadgeCheck className="h-3.5 w-3.5 shrink-0 text-primary" />
                    )}
                  </div>
                  {p.description && (
                    <p className="text-[11px] text-muted-foreground truncate max-w-[200px] mt-0.5">
                      {p.description.length > 60 ? `${p.description.slice(0, 60)}...` : p.description}
                    </p>
                  )}
                </TableCell>

                {/* Asset type */}
                <TableCell className="py-2.5 text-center">
                  <span className="text-xs text-muted-foreground">
                    {ASSET_SHORT[p.asset_class] ?? p.asset_class}
                  </span>
                </TableCell>

                {/* Win Rate */}
                <TableCell className="py-2.5 text-right">
                  <span className={cn(
                    "text-sm font-medium tabular-nums",
                    !hasData ? "text-muted-foreground" :
                    wr! >= 60 ? "text-emerald-400" :
                    wr! >= 45 ? "text-foreground" : "text-rose-400",
                  )}>
                    {hasData ? `${wr!.toFixed(1)}%` : "—"}
                  </span>
                </TableCell>

                {/* P&L */}
                <TableCell className="py-2.5 text-right">
                  <span className={cn(
                    "text-sm font-medium tabular-nums",
                    p.total_pnl_pips === null ? "text-muted-foreground" :
                    p.total_pnl_pips >= 0 ? "text-emerald-400" : "text-rose-400",
                  )}>
                    {fmtPips(p.total_pnl_pips, true)}
                  </span>
                </TableCell>

                {/* Max Drawdown */}
                <TableCell className="py-2.5 text-right">
                  <span className={cn(
                    "text-sm tabular-nums",
                    p.max_drawdown_pips === null ? "text-muted-foreground" : "text-rose-400",
                  )}>
                    {p.max_drawdown_pips !== null ? `-${Math.round(Math.abs(p.max_drawdown_pips))}p` : "—"}
                  </span>
                </TableCell>

                {/* Signals */}
                <TableCell className="py-2.5 text-right">
                  <span className="text-sm tabular-nums text-foreground">
                    {p.signal_count}
                  </span>
                </TableCell>

                {/* Followers */}
                <TableCell className="py-2.5 text-right">
                  <span className="text-sm tabular-nums text-muted-foreground">
                    {p.subscriber_count}
                  </span>
                </TableCell>

                {/* Track Record */}
                <TableCell className="py-2.5 text-right">
                  <span className="text-xs tabular-nums text-muted-foreground">
                    {p.track_record_days}d
                  </span>
                </TableCell>

                {/* Action */}
                <TableCell className="py-2.5 text-right">
                  {isFollowing ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-[10px] text-emerald-500 hover:text-rose-400 hover:bg-rose-500/5"
                      onClick={() => onUnsubscribe(p.id)}
                    >
                      Following
                    </Button>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-[10px] text-primary hover:text-primary hover:bg-primary/5"
                      onClick={() => onSubscribe(p)}
                    >
                      Follow
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
