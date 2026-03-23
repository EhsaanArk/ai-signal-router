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

interface ProviderTableProps {
  providers: MarketplaceProvider[];
  subscribedIds: Set<string>;
  onSubscribe: (provider: MarketplaceProvider) => void;
  onUnsubscribe: (providerId: string) => void;
}

function fmtPips(v: number | null, sign = false): string {
  if (v === null) return "—";
  const prefix = sign && v > 0 ? "+" : "";
  const n = Math.abs(v) >= 1000
    ? v.toLocaleString(undefined, { maximumFractionDigits: 0 })
    : Number.isInteger(v) ? v.toString() : v.toFixed(1);
  return `${prefix}${n}p`;
}

const ASSET_SHORT: Record<string, string> = {
  forex: "FX",
  crypto: "Crypto",
  both: "Multi",
};

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
                className="border-border/30 hover:bg-accent/5 transition-colors"
              >
                {/* Provider name */}
                <TableCell className="py-2.5">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-medium truncate max-w-[180px]">
                      {p.name}
                    </span>
                    <BadgeCheck className="h-3.5 w-3.5 shrink-0 text-primary/50" />
                  </div>
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
                    !hasData ? "text-muted-foreground/40" :
                    wr! >= 60 ? "text-emerald-400/90" :
                    wr! >= 45 ? "text-foreground" : "text-rose-400/90",
                  )}>
                    {hasData ? `${wr!.toFixed(1)}%` : "—"}
                  </span>
                </TableCell>

                {/* P&L */}
                <TableCell className="py-2.5 text-right">
                  <span className={cn(
                    "text-sm font-medium tabular-nums",
                    p.total_pnl_pips === null ? "text-muted-foreground/40" :
                    p.total_pnl_pips >= 0 ? "text-emerald-400/90" : "text-rose-400/90",
                  )}>
                    {fmtPips(p.total_pnl_pips, true)}
                  </span>
                </TableCell>

                {/* Max Drawdown */}
                <TableCell className="py-2.5 text-right">
                  <span className={cn(
                    "text-sm tabular-nums",
                    p.max_drawdown_pips === null ? "text-muted-foreground/40" : "text-rose-400/70",
                  )}>
                    {p.max_drawdown_pips !== null ? `-${Math.round(Math.abs(p.max_drawdown_pips))}p` : "—"}
                  </span>
                </TableCell>

                {/* Signals */}
                <TableCell className="py-2.5 text-right">
                  <span className="text-sm tabular-nums text-foreground/80">
                    {p.signal_count}
                  </span>
                </TableCell>

                {/* Followers */}
                <TableCell className="py-2.5 text-right">
                  <span className="text-sm tabular-nums text-foreground/60">
                    {p.subscriber_count}
                  </span>
                </TableCell>

                {/* Track Record */}
                <TableCell className="py-2.5 text-right">
                  <span className="text-xs tabular-nums text-muted-foreground/60">
                    {p.track_record_days}d
                  </span>
                </TableCell>

                {/* Action */}
                <TableCell className="py-2.5 text-right">
                  {isFollowing ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-[10px] text-emerald-500/80 hover:text-rose-400 hover:bg-rose-500/5"
                      onClick={() => onUnsubscribe(p.id)}
                    >
                      Following
                    </Button>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-[10px] text-primary/70 hover:text-primary hover:bg-primary/5"
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
