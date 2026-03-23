import { BadgeCheck } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
  return `-${Math.abs(dd).toFixed(1)}%`;
}

function formatWinRate(rate: number | null): string {
  if (rate === null) return "--";
  return `${Math.round(rate)}%`;
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
  const trackProgress = Math.min(provider.track_record_days / 180, 1);
  const pnlPositive = provider.total_pnl_pips !== null && provider.total_pnl_pips >= 0;

  return (
    <Card className="group relative flex flex-col transition-all duration-200 hover:scale-[1.01] hover:shadow-lg">
      <CardContent className="flex flex-1 flex-col gap-4 p-5">
        {/* Header: Name + badges */}
        <div className="space-y-1.5">
          <h3 className="text-sm font-semibold leading-tight truncate">
            {provider.name}
          </h3>
          <div className="flex items-center gap-2">
            {provider.is_verified && (
              <Badge
                variant="outline"
                className="gap-1 border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400 text-[10px] px-1.5 py-0"
              >
                <BadgeCheck className="h-3 w-3" />
                Verified
              </Badge>
            )}
            <Badge
              variant="secondary"
              className="text-[10px] px-1.5 py-0 text-muted-foreground"
            >
              {ASSET_LABELS[provider.asset_class] ?? provider.asset_class}
            </Badge>
          </div>
        </div>

        {/* Stats row — the star of the card */}
        <div className="grid grid-cols-3 gap-3 text-center">
          {/* Win Rate */}
          <div>
            <p
              className={cn(
                "text-2xl font-bold tabular-nums leading-none",
                provider.win_rate !== null && provider.win_rate >= 60
                  ? "text-emerald-500"
                  : provider.win_rate !== null && provider.win_rate < 45
                    ? "text-rose-500"
                    : "text-foreground",
              )}
            >
              {formatWinRate(provider.win_rate)}
            </p>
            <p className="mt-1 text-[10px] text-muted-foreground">win</p>
          </div>

          {/* P&L */}
          <div>
            <p
              className={cn(
                "text-2xl font-bold tabular-nums leading-none",
                pnlPositive ? "text-emerald-500" : "text-rose-500",
                provider.total_pnl_pips === null && "text-zinc-400",
              )}
            >
              {formatPnl(provider.total_pnl_pips)}
            </p>
            <p className="mt-1 text-[10px] text-muted-foreground">P&L</p>
          </div>

          {/* Drawdown */}
          <div>
            <p
              className={cn(
                "text-2xl font-bold tabular-nums leading-none",
                provider.max_drawdown_pips !== null
                  ? "text-rose-400"
                  : "text-zinc-400",
              )}
            >
              {formatDrawdown(provider.max_drawdown_pips)}
            </p>
            <p className="mt-1 text-[10px] text-muted-foreground">DD</p>
          </div>
        </div>

        {/* Track record bar */}
        <div className="space-y-1">
          <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-primary/60 transition-all duration-500"
              style={{ width: `${trackProgress * 100}%` }}
            />
          </div>
          <p className="text-[10px] text-muted-foreground text-right tabular-nums">
            {provider.track_record_days}d track record
          </p>
        </div>

        {/* Meta row */}
        <div className="flex items-center justify-between text-[11px] text-muted-foreground tabular-nums">
          <span>{provider.signal_count.toLocaleString()} signals</span>
          <span className="h-1 w-1 rounded-full bg-zinc-400" />
          <span>{provider.subscriber_count.toLocaleString()} subscribers</span>
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
      </CardContent>
    </Card>
  );
}
