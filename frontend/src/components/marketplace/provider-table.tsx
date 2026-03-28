import { BadgeCheck, Sparkles } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { MarketplaceProvider } from "@/types/marketplace";
import { ASSET_SHORT } from "./format";

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
            <TableHead className="w-[240px] text-[11px] font-medium">Provider</TableHead>
            <TableHead className="w-[60px] text-[11px] font-medium text-center">Type</TableHead>
            <TableHead className="w-[90px] text-[11px] font-medium text-right">Reliability</TableHead>
            <TableHead className="w-[70px] text-[11px] font-medium text-right">Signals</TableHead>
            <TableHead className="w-[70px] text-[11px] font-medium text-right">Followers</TableHead>
            <TableHead className="w-[70px] text-[11px] font-medium text-right">Track</TableHead>
            <TableHead className="w-[90px] text-[11px] font-medium text-right"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {providers.map((p) => {
            const isFollowing = subscribedIds.has(p.id);
            const wr = p.win_rate;
            const hasData = wr !== null;
            const isVerified = p.is_verified;
            const isNew = !isVerified;

            return (
              <TableRow
                key={p.id}
                role="article"
                aria-label={`${p.name} - ${hasData ? `${wr!.toFixed(1)}% reliability` : "new provider"}`}
                className="border-border/30 hover:bg-accent/5 transition-colors"
              >
                {/* Provider name + badge */}
                <TableCell className="py-2.5">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-medium truncate max-w-[180px]">
                      {p.name}
                    </span>
                    {isVerified ? (
                      <Tooltip delayDuration={0}>
                        <TooltipTrigger asChild>
                          <BadgeCheck className="h-3.5 w-3.5 shrink-0 text-primary" />
                        </TooltipTrigger>
                        <TooltipContent side="top">
                          Verified: 30+ days tracked, 20+ signals
                        </TooltipContent>
                      </Tooltip>
                    ) : (
                      <span className="shrink-0 text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground">
                        New
                      </span>
                    )}
                  </div>
                  {p.description && (
                    <p className="text-[11px] text-muted-foreground line-clamp-1 max-w-[220px] mt-0.5">
                      {p.description}
                    </p>
                  )}
                </TableCell>

                {/* Asset type */}
                <TableCell className="py-2.5 text-center">
                  <span className="text-xs text-muted-foreground">
                    {ASSET_SHORT[p.asset_class] ?? p.asset_class}
                  </span>
                </TableCell>

                {/* Signal Reliability */}
                <TableCell className="py-2.5 text-right">
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <span className={cn(
                        "text-sm font-medium tabular-nums",
                        !hasData ? "text-muted-foreground" :
                        isNew ? "text-muted-foreground" : "text-foreground",
                      )}>
                        {hasData ? `${wr!.toFixed(1)}%` : "—"}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                      Signal reliability: % of signals successfully parsed and routed
                    </TooltipContent>
                  </Tooltip>
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
                      variant="outline"
                      size="sm"
                      className="h-7 px-3 text-xs text-emerald-500 border-emerald-500/20 hover:text-rose-400 hover:border-rose-500/20 hover:bg-rose-500/5"
                      onClick={() => onUnsubscribe(p.id)}
                    >
                      Following
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 px-3 text-xs text-primary border-primary/20 hover:bg-primary/5"
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
