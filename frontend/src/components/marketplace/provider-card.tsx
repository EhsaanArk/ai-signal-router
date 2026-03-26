import { BadgeCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { MarketplaceProvider } from "@/types/marketplace";
import { ASSET_SHORT } from "./format";

interface ProviderCardProps {
  provider: MarketplaceProvider;
  isSubscribed: boolean;
  onSubscribe: (provider: MarketplaceProvider) => void;
  onUnsubscribe: (providerId: string) => void;
}

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
  const hasData = wr !== null;
  const isVerified = provider.is_verified;

  return (
    <div
      role="article"
      aria-label={`${provider.name} - ${hasData ? `${wr!.toFixed(1)}% reliability` : "new provider"}`}
      className="rounded-md border border-border/40 bg-card px-4 py-3 transition-colors hover:bg-accent/5"
    >
      {/* Row 1: Identity */}
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-1.5 min-w-0">
          <h3 className="text-sm font-medium truncate">{provider.name}</h3>
          {isVerified ? (
            <BadgeCheck className="h-3.5 w-3.5 shrink-0 text-primary" />
          ) : (
            <span className="shrink-0 text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground">
              New
            </span>
          )}
        </div>
        <span className="shrink-0 text-[10px] text-muted-foreground">
          {ASSET_SHORT[provider.asset_class] ?? provider.asset_class}
        </span>
      </div>
      {provider.description && (
        <p className="text-[11px] text-muted-foreground line-clamp-1 mb-2.5">
          {provider.description}
        </p>
      )}
      {!provider.description && <div className="mb-1.5" />}

      {/* Row 2: Stats — horizontal, equal weight */}
      <div className="flex items-baseline gap-4 mb-2.5">
        <div>
          <span className={cn(
            "text-sm font-semibold tabular-nums",
            !hasData ? "text-muted-foreground" :
            isVerified ? "text-foreground" : "text-muted-foreground",
          )}>
            {hasData ? `${wr!.toFixed(1)}%` : "—"}
          </span>
          <span className="ml-1 text-[10px] text-muted-foreground">reliability</span>
        </div>
        <div>
          <span className="text-sm tabular-nums text-foreground">{provider.signal_count}</span>
          <span className="ml-0.5 text-[10px] text-muted-foreground">sig</span>
        </div>
        <div>
          <span className="text-sm tabular-nums text-muted-foreground">{provider.subscriber_count}</span>
          <span className="ml-0.5 text-[10px] text-muted-foreground">followers</span>
        </div>
      </div>

      {/* Row 3: Track record + Action */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">
            {provider.track_record_days}d tracked
          </span>
          <div className="w-12 h-1 rounded-full bg-primary/20 shrink-0">
            <div
              className="h-1 rounded-full bg-primary"
              style={{ width: `${Math.min(100, Math.round((provider.track_record_days / 90) * 100))}%` }}
            />
          </div>
        </div>
        {isSubscribed ? (
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-3 text-xs text-emerald-500 border-emerald-500/20 hover:text-rose-400 hover:border-rose-500/20 hover:bg-rose-500/5"
            onClick={() => onUnsubscribe(provider.id)}
          >
            Following
          </Button>
        ) : (
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-3 text-xs text-primary border-primary/20 hover:bg-primary/5"
            onClick={() => onSubscribe(provider)}
          >
            Follow
          </Button>
        )}
      </div>
    </div>
  );
}
