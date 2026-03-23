import { useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertTriangle, Radio, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { ProviderCard } from "@/components/marketplace/provider-card";
import { SubscribeSheet } from "@/components/marketplace/subscribe-sheet";
import { MarketplaceFilters } from "@/components/marketplace/marketplace-filters";
import {
  useMarketplaceProviders,
  useSubscribe,
  useUnsubscribe,
  useMySubscriptions,
} from "@/hooks/use-marketplace";
import { useAuth } from "@/contexts/auth-context";
import { usePageTitle } from "@/hooks/use-page-title";
import { cn } from "@/lib/utils";
import type { MarketplaceProvider } from "@/types/marketplace";
import type { MarketplaceSort, MarketplaceFilter } from "@/types/marketplace";

export function MarketplacePage() {
  usePageTitle("Signal Marketplace");
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const sort = (searchParams.get("sort") as MarketplaceSort) || "win_rate";
  const filter = (searchParams.get("filter") as MarketplaceFilter) || "all";

  const setSort = useCallback(
    (s: MarketplaceSort) => {
      setSearchParams((prev) => { prev.set("sort", s); return prev; });
    },
    [setSearchParams],
  );

  const setFilter = useCallback(
    (f: MarketplaceFilter) => {
      setSearchParams((prev) => {
        if (f === "all") prev.delete("filter"); else prev.set("filter", f);
        return prev;
      });
    },
    [setSearchParams],
  );

  const { data: providers, isLoading, isError, refetch, isFetching } =
    useMarketplaceProviders(sort, filter);
  const { data: subscriptions } = useMySubscriptions(!!user);
  const subscribeMutation = useSubscribe();
  const unsubscribeMutation = useUnsubscribe();

  const [sheetProvider, setSheetProvider] = useState<MarketplaceProvider | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  const subscribedIds = new Set(
    subscriptions?.filter((s) => s.is_active).map((s) => s.provider_id) ?? [],
  );

  function handleSubscribeClick(provider: MarketplaceProvider) {
    setSheetProvider(provider);
    setSheetOpen(true);
  }

  function handleConfirmSubscribe(providerId: string, webhookDestinationId?: string) {
    subscribeMutation.mutate(
      { providerId, webhookDestinationId: webhookDestinationId ?? "" },
      {
        onSuccess: () => {
          toast.success(`Now following ${sheetProvider?.name ?? "provider"}`);
          setSheetOpen(false);
          setSheetProvider(null);
        },
        onError: (err) => {
          toast.error(err instanceof Error ? err.message : "Failed to subscribe");
        },
      },
    );
  }

  function handleUnsubscribe(providerId: string) {
    unsubscribeMutation.mutate(providerId, {
      onSuccess: () => toast.success("Unfollowed"),
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "Failed to unsubscribe"),
    });
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-foreground">
            Signal Marketplace
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Verified providers ranked by Sage Intelligence
            {providers && providers.length > 0 && (
              <span className="text-muted-foreground/50"> · {providers.length} providers</span>
            )}
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-muted-foreground"
          onClick={() => refetch()}
          aria-label="Refresh"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />
        </Button>
      </div>

      {/* Filters */}
      <div className="mb-4 pb-3 border-b border-border/40">
        <MarketplaceFilters
          sort={sort}
          filter={filter}
          onSortChange={setSort}
          onFilterChange={setFilter}
        />
      </div>

      {/* Error */}
      {isError && (
        <div className="mb-4 flex items-center gap-2 rounded-md border border-rose-500/20 bg-rose-500/5 px-3 py-2">
          <AlertTriangle className="h-3.5 w-3.5 text-rose-400 shrink-0" />
          <p className="flex-1 text-xs text-rose-400">Failed to load providers.</p>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-[11px] text-rose-400"
            onClick={() => refetch()}
          >
            Retry
          </Button>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-md border border-border/50 bg-card/80 p-4">
              <div className="flex items-center gap-2 mb-3">
                <Skeleton className="h-8 w-8 rounded-md" />
                <div className="flex-1">
                  <Skeleton className="h-3.5 w-3/4 mb-1" />
                  <Skeleton className="h-2.5 w-16" />
                </div>
              </div>
              <div className="grid grid-cols-4 gap-px rounded-md overflow-hidden">
                {[1, 2, 3, 4].map((n) => (
                  <div key={n} className="bg-card p-2.5 flex flex-col items-center gap-1">
                    <Skeleton className="h-2 w-10" />
                    <Skeleton className="h-5 w-8" />
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-border/30">
                <Skeleton className="h-2.5 w-24" />
                <Skeleton className="h-7 w-16 rounded-md" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty */}
      {!isLoading && !isError && providers?.length === 0 && (
        <EmptyState
          icon={Radio}
          title="No providers found"
          description={
            filter !== "all"
              ? `No ${filter} providers available. Try a different filter.`
              : "No signal providers listed yet. Check back soon."
          }
        />
      )}

      {/* Grid */}
      {!isLoading && providers && providers.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {providers.map((provider) => (
            <ProviderCard
              key={provider.id}
              provider={provider}
              isSubscribed={subscribedIds.has(provider.id)}
              onSubscribe={handleSubscribeClick}
              onUnsubscribe={handleUnsubscribe}
            />
          ))}
        </div>
      )}

      {/* Disclaimer */}
      <p className="mt-6 text-center text-[10px] text-muted-foreground/40 leading-relaxed">
        Past performance is not indicative of future results. Statistics computed
        by Sage Intelligence based on historical signal data.
      </p>

      <SubscribeSheet
        provider={sheetProvider}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        onConfirm={handleConfirmSubscribe}
        isLoading={subscribeMutation.isPending}
      />
    </div>
  );
}

export default MarketplacePage;
