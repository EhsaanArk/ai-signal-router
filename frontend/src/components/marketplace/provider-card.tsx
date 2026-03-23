import { BadgeCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { MarketplaceProvider } from "@/types/marketplace";

interface ProviderCardProps {
  provider: MarketplaceProvider;
  isSubscribed: boolean;
  onSubscribe: (provider: MarketplaceProvider) => void;
  onUnsubscribe: (providerId: string) => void;
}

function fmtPips(v: number | null, sign = false): string {
  if (v === null) return "—";
  const prefix = sign && v > 0 ? "+" : "";
  const n = Math.abs(v) >= 1000
    ? v.toLocaleString(undefined, { maximumFractionDigits: 0 })
    : Number.isInteger(v) ? v.toString() : v.toFixed(1);
  return `${prefix}${n}`;
}

const ASSET_SHORT: Record<string, string> = {
  forex: "FX",
  crypto: "Crypto",
  both: "Multi",
};

/**
 * Mobile card — used on small screens where the table doesn't fit.
 * Designed as a compressed data row, NOT a marketing card.
 */
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

  return (
    <div className="rounded-md border border-border/40 bg-card px-4 py-3 transition-colors hover:bg-accent/5">
      {/* Row 1: Identity */}
      <div className="flex items-center justify-between gap-2 mb-2.5">
        <div className="flex items-center gap-1.5 min-w-0">
          <h3 className="text-sm font-medium truncate">{provider.name}</h3>
          <BadgeCheck className="h-3.5 w-3.5 shrink-0 text-primary/60" />
        </div>
        <span className="shrink-0 text-[10px] text-muted-foreground/70">
          {ASSET_SHORT[provider.asset_class] ?? provider.asset_class}
        </span>
      </div>

      {/* Row 2: Stats — horizontal, equal weight */}
      <div className="flex items-baseline gap-4 mb-2.5">
        <div>
          <span className={cn(
            "text-sm font-semibold tabular-nums",
            !hasData ? "text-muted-foreground/40" :
            wr! >= 60 ? "text-emerald-400/90" :
            wr! >= 45 ? "text-foreground" : "text-rose-400/90",
          )}>
            {hasData ? `${Math.round(wr!)}%` : "—"}
          </span>
          <span className="ml-1 text-[10px] text-muted-foreground/50">win</span>
        </div>
        <div>
          <span className={cn(
            "text-sm font-semibold tabular-nums",
            pnl === null ? "text-muted-foreground/40" :
            pnl >= 0 ? "text-emerald-400/90" : "text-rose-400/90",
          )}>
            {fmtPips(pnl, true)}
          </span>
          <span className="ml-0.5 text-[10px] text-muted-foreground/50">p</span>
        </div>
        <div>
          <span className={cn(
            "text-sm font-semibold tabular-nums",
            dd === null ? "text-muted-foreground/40" : "text-rose-400/70",
          )}>
            {dd !== null ? `-${Math.round(Math.abs(dd))}` : "—"}
          </span>
          <span className="ml-0.5 text-[10px] text-muted-foreground/50">dd</span>
        </div>
        <div>
          <span className="text-sm tabular-nums text-foreground/70">{provider.signal_count}</span>
          <span className="ml-0.5 text-[10px] text-muted-foreground/50">sig</span>
        </div>
      </div>

      {/* Row 3: Meta + Action */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-muted-foreground/50 tabular-nums">
          {provider.subscriber_count} followers · {provider.track_record_days}d tracked
        </span>
        {isSubscribed ? (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-[10px] text-emerald-500/80 hover:text-rose-400 hover:bg-rose-500/5"
            onClick={() => onUnsubscribe(provider.id)}
          >
            Following
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-[10px] text-primary/70 hover:text-primary hover:bg-primary/5"
            onClick={() => onSubscribe(provider)}
          >
            Follow
          </Button>
        )}
      </div>
    </div>
  );
}
