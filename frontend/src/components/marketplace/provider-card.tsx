import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { MarketplaceProvider } from "@/types/marketplace";

interface ProviderCardProps {
  provider: MarketplaceProvider;
  isSubscribed: boolean;
  onSubscribe: (provider: MarketplaceProvider) => void;
  onUnsubscribe: (providerId: string) => void;
}

function formatPnl(pips: number | null): string {
  if (pips === null) return "--";
  const sign = pips >= 0 ? "+" : "";
  return `${sign}${pips.toLocaleString()}p`;
}

function formatDrawdown(dd: number | null): string {
  if (dd === null) return "--";
  return `-${Math.abs(dd).toFixed(0)}p`;
}

function formatWinRate(rate: number | null): string {
  if (rate === null) return "--";
  return `${Math.round(rate)}%`;
}

/** Performance tier based on win rate */
function getTierColor(winRate: number | null): {
  border: string;
  text: string;
  glow: string;
} {
  if (winRate === null || winRate < 45)
    return {
      border: "border-l-rose-500",
      text: "text-rose-500",
      glow: "hover:shadow-rose-500/10",
    };
  if (winRate < 60)
    return {
      border: "border-l-foreground/40",
      text: "text-foreground",
      glow: "hover:shadow-foreground/5",
    };
  return {
    border: "border-l-emerald-500",
    text: "text-emerald-500",
    glow: "hover:shadow-emerald-500/10",
  };
}

const ASSET_LABELS: Record<string, string> = {
  forex: "FX",
  crypto: "Crypto",
  both: "Multi",
};

export function ProviderCard({
  provider,
  isSubscribed,
  onSubscribe,
  onUnsubscribe,
}: ProviderCardProps) {
  const trackProgress = Math.min(provider.track_record_days / 180, 1);
  const pnlPositive =
    provider.total_pnl_pips !== null && provider.total_pnl_pips >= 0;
  const tier = getTierColor(provider.win_rate);

  return (
    <div
      className={cn(
        "group relative flex flex-col rounded-lg border border-border/60 bg-card",
        "border-l-2 transition-shadow duration-200",
        tier.border,
        tier.glow,
        "hover:shadow-lg",
      )}
    >
      {/* Track record gradient — subtle fill behind card bottom */}
      <div className="absolute inset-x-0 bottom-0 h-16 overflow-hidden rounded-b-lg pointer-events-none">
        <div
          className="absolute bottom-0 left-0 h-full bg-gradient-to-r from-primary/[0.04] to-transparent"
          style={{ width: `${trackProgress * 100}%` }}
        />
      </div>

      <div className="relative flex flex-1 flex-col gap-3 p-4">
        {/* Header row: name + asset pill */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-semibold leading-tight truncate">
              {provider.name}
            </h3>
            <span className="inline-flex items-center gap-1 mt-0.5 text-[10px] text-emerald-500/80">
              <Check className="h-2.5 w-2.5" />
              Verified
            </span>
          </div>
          <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
            {ASSET_LABELS[provider.asset_class] ?? provider.asset_class}
          </span>
        </div>

        {/* HERO: Win Rate */}
        <div className="py-1">
          <p
            className={cn(
              "text-4xl font-black tabular-nums leading-none tracking-tight",
              tier.text,
            )}
          >
            {formatWinRate(provider.win_rate)}
          </p>
          <p className="mt-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            Win Rate
          </p>
        </div>

        {/* Secondary stats: P&L + Drawdown side by side */}
        <div className="flex gap-4">
          <div>
            <p
              className={cn(
                "text-base font-semibold tabular-nums leading-none",
                provider.total_pnl_pips === null
                  ? "text-muted-foreground"
                  : pnlPositive
                    ? "text-emerald-500"
                    : "text-rose-500",
              )}
            >
              {formatPnl(provider.total_pnl_pips)}
            </p>
            <p className="mt-0.5 text-[10px] text-muted-foreground">P&L</p>
          </div>
          <div>
            <p
              className={cn(
                "text-base font-semibold tabular-nums leading-none",
                provider.max_drawdown_pips !== null
                  ? "text-rose-400"
                  : "text-muted-foreground",
              )}
            >
              {formatDrawdown(provider.max_drawdown_pips)}
            </p>
            <p className="mt-0.5 text-[10px] text-muted-foreground">
              Drawdown
            </p>
          </div>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground/70 tabular-nums">
          <span>{provider.signal_count.toLocaleString()} signals</span>
          <span className="h-0.5 w-0.5 rounded-full bg-muted-foreground/30" />
          <span>
            {provider.subscriber_count.toLocaleString()} subscribers
          </span>
          <span className="h-0.5 w-0.5 rounded-full bg-muted-foreground/30" />
          <span>{provider.track_record_days}d record</span>
        </div>

        {/* Action */}
        <div className="mt-auto pt-1">
          {isSubscribed ? (
            <Button
              variant="outline"
              size="sm"
              className="w-full text-emerald-600 dark:text-emerald-400 border-emerald-500/30 hover:bg-rose-500/10 hover:text-rose-600 hover:border-rose-500/30 dark:hover:text-rose-400 transition-colors"
              onClick={() => onUnsubscribe(provider.id)}
            >
              Subscribed
            </Button>
          ) : (
            <Button
              size="sm"
              className="w-full"
              onClick={() => onSubscribe(provider)}
            >
              Subscribe
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
