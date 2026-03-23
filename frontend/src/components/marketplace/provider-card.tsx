import { BadgeCheck, BarChart3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { MarketplaceProvider } from "@/types/marketplace";

interface ProviderCardProps {
  provider: MarketplaceProvider;
  isSubscribed: boolean;
  onSubscribe: (provider: MarketplaceProvider) => void;
  onUnsubscribe: (providerId: string) => void;
}

function fmt(v: number | null, opts?: { sign?: boolean; suffix?: string }): string {
  if (v === null) return "—";
  const s = opts?.sign && v > 0 ? "+" : "";
  const n = Math.abs(v) >= 1000 ? v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : v % 1 === 0 ? v.toString() : v.toFixed(1);
  return `${s}${n}${opts?.suffix ?? ""}`;
}

const ASSET_LABELS: Record<string, string> = {
  forex: "Forex",
  crypto: "Crypto",
  both: "Multi-Asset",
};

export function ProviderCard({
  provider,
  isSubscribed,
  onSubscribe,
  onUnsubscribe,
}: ProviderCardProps) {
  const wr = provider.win_rate;
  const pnl = provider.total_pnl_pips;
  const dd = provider.max_drawdown_pips;
  const hasData = wr !== null;
  const isPositive = pnl !== null && pnl >= 0;

  return (
    <div
      className={cn(
        "flex flex-col rounded-md border border-border/50 bg-card/80 backdrop-blur-sm",
        "transition-all duration-150",
        "hover:border-border hover:bg-card",
      )}
    >
      {/* Top section — identity + primary metric */}
      <div className="px-4 pt-4 pb-3">
        {/* Row 1: Name + Asset tag */}
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2 min-w-0">
            {/* Provider initial avatar */}
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted/80 text-xs font-semibold text-muted-foreground">
              {provider.name.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0">
              <h3 className="text-[13px] font-medium leading-tight truncate text-foreground">
                {provider.name}
              </h3>
              <div className="flex items-center gap-1 mt-0.5">
                <BadgeCheck className="h-3 w-3 text-primary/70" />
                <span className="text-[10px] text-primary/70 font-medium">Verified</span>
              </div>
            </div>
          </div>
          <span className="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium bg-muted/60 text-muted-foreground">
            {ASSET_LABELS[provider.asset_class] ?? provider.asset_class}
          </span>
        </div>

        {/* Row 2: Stats grid — clean, aligned, scannable */}
        <div className="grid grid-cols-4 gap-px rounded-md overflow-hidden bg-border/30">
          {/* Win Rate */}
          <div className="bg-card px-2.5 py-2.5 text-center">
            <p className="text-[10px] text-muted-foreground/70 mb-1">Win Rate</p>
            <p className={cn(
              "text-lg font-semibold tabular-nums leading-none",
              !hasData ? "text-muted-foreground/40" :
              wr! >= 65 ? "text-emerald-400" :
              wr! >= 50 ? "text-foreground" :
              "text-rose-400",
            )}>
              {hasData ? `${Math.round(wr!)}%` : "—"}
            </p>
          </div>

          {/* P&L */}
          <div className="bg-card px-2.5 py-2.5 text-center">
            <p className="text-[10px] text-muted-foreground/70 mb-1">P&L</p>
            <p className={cn(
              "text-lg font-semibold tabular-nums leading-none",
              pnl === null ? "text-muted-foreground/40" :
              isPositive ? "text-emerald-400" : "text-rose-400",
            )}>
              {fmt(pnl, { sign: true, suffix: "p" })}
            </p>
          </div>

          {/* Drawdown */}
          <div className="bg-card px-2.5 py-2.5 text-center">
            <p className="text-[10px] text-muted-foreground/70 mb-1">Max DD</p>
            <p className={cn(
              "text-lg font-semibold tabular-nums leading-none",
              dd === null ? "text-muted-foreground/40" : "text-rose-400/80",
            )}>
              {dd !== null ? `-${Math.round(Math.abs(dd))}p` : "—"}
            </p>
          </div>

          {/* Signals */}
          <div className="bg-card px-2.5 py-2.5 text-center">
            <p className="text-[10px] text-muted-foreground/70 mb-1">Signals</p>
            <p className="text-lg font-semibold tabular-nums leading-none text-foreground/90">
              {provider.signal_count}
            </p>
          </div>
        </div>
      </div>

      {/* Bottom section — meta + action */}
      <div className="mt-auto border-t border-border/30 px-4 py-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground/60 tabular-nums">
          <span className="flex items-center gap-1">
            <BarChart3 className="h-3 w-3" />
            {provider.track_record_days}d
          </span>
          <span>{provider.subscriber_count} followers</span>
        </div>

        {isSubscribed ? (
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-3 text-[11px] text-emerald-500 hover:text-rose-400 hover:bg-rose-500/10"
            onClick={() => onUnsubscribe(provider.id)}
          >
            Following
          </Button>
        ) : (
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-4 text-[11px]"
            onClick={() => onSubscribe(provider)}
          >
            Follow
          </Button>
        )}
      </div>
    </div>
  );
}
