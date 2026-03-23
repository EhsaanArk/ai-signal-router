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

  // URL-driven sort/filter state
  const sort = (searchParams.get("sort") as MarketplaceSort) || "win_rate";
  const filter = (searchParams.get("filter") as MarketplaceFilter) || "all";

  const setSort = useCallback(
    (s: MarketplaceSort) => {
      setSearchParams((prev) => {
        prev.set("sort", s);
        return prev;
      });
    },
    [setSearchParams],
  );

  const setFilter = useCallback(
    (f: MarketplaceFilter) => {
      setSearchParams((prev) => {
        if (f === "all") {
          prev.delete("filter");
        } else {
          prev.set("filter", f);
        }
        return prev;
      });
    },
    [setSearchParams],
  );

  // Data
  const {
    data: providers,
    isLoading,
    isError,
    refetch,
    isFetching,
  } = useMarketplaceProviders(sort, filter);

  const { data: subscriptions } = useMySubscriptions(!!user);
  const subscribeMutation = useSubscribe();
  const unsubscribeMutation = useUnsubscribe();

  // Subscribe sheet state
  const [sheetProvider, setSheetProvider] = useState<MarketplaceProvider | null>(
    null,
  );
  const [sheetOpen, setSheetOpen] = useState(false);

  const subscribedIds = new Set(
    subscriptions
      ?.filter((s) => s.is_active)
      .map((s) => s.provider_id) ?? [],
  );

  function handleSubscribeClick(provider: MarketplaceProvider) {
    setSheetProvider(provider);
    setSheetOpen(true);
  }

  function handleConfirmSubscribe(providerId: string, webhookDestinationId?: string) {
    subscribeMutation.mutate({ providerId, webhookDestinationId: webhookDestinationId ?? "" }, {
      onSuccess: () => {
        toast.success(`Subscribed to ${sheetProvider?.name ?? "provider"}`);
        setSheetOpen(false);
        setSheetProvider(null);
      },
      onError: (err) => {
        toast.error(
          err instanceof Error ? err.message : "Failed to subscribe",
        );
      },
    });
  }

  function handleUnsubscribe(providerId: string) {
    unsubscribeMutation.mutate(providerId, {
      onSuccess: () => {
        toast.success("Unsubscribed");
      },
      onError: (err) => {
        toast.error(
          err instanceof Error ? err.message : "Failed to unsubscribe",
        );
      },
    });
  }

  const providerCount = providers?.length ?? 0;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header area with subtle atmosphere */}
      <div className="relative mb-6">
        {/* Subtle radial gradient for atmosphere */}
        <div className="absolute -inset-x-4 -top-8 h-32 bg-gradient-to-b from-primary/[0.03] to-transparent rounded-xl pointer-events-none" />

        <div className="relative space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">
              Signal Marketplace
            </h1>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => refetch()}
              aria-label="Refresh marketplace"
            >
              <RefreshCw
                className={cn("h-3.5 w-3.5", isFetching && "animate-spin")}
              />
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Verified providers ranked by Sage Intelligence
            {!isLoading && providerCount > 0 && (
              <span className="ml-1.5 text-muted-foreground/50">
                &middot; {providerCount} provider{providerCount !== 1 ? "s" : ""}
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Sort / Filter bar — integrated with tighter spacing */}
      <div className="mb-5 flex items-center gap-3 border-b border-border/40 pb-3">
        <MarketplaceFilters
          sort={sort}
          filter={filter}
          onSortChange={setSort}
          onFilterChange={setFilter}
        />
      </div>

      {/* Error banner */}
      {isError && (
        <div className="mb-5 flex items-center gap-2 rounded-md border border-rose-500/20 bg-rose-500/10 px-3 py-2">
          <AlertTriangle className="h-3.5 w-3.5 text-rose-500 shrink-0" />
          <p className="flex-1 text-xs text-rose-600 dark:text-rose-400">
            Failed to load providers.
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-[11px] text-rose-600 dark:text-rose-400"
            onClick={() => refetch()}
          >
            Retry
          </Button>
        </div>
      )}

      {/* Loading skeleton grid */}
      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-lg border border-border/60 bg-card border-l-2 border-l-muted p-4">
              <div className="space-y-3">
                <div className="flex justify-between">
                  <div className="space-y-1.5 flex-1">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-2.5 w-16" />
                  </div>
                  <Skeleton className="h-5 w-12 rounded-full" />
                </div>
                <div className="space-y-1 py-1">
                  <Skeleton className="h-10 w-20" />
                  <Skeleton className="h-2.5 w-14" />
                </div>
                <div className="flex gap-4">
                  <div className="space-y-1">
                    <Skeleton className="h-5 w-16" />
                    <Skeleton className="h-2 w-8" />
                  </div>
                  <div className="space-y-1">
                    <Skeleton className="h-5 w-14" />
                    <Skeleton className="h-2 w-12" />
                  </div>
                </div>
                <Skeleton className="h-2.5 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && providers?.length === 0 && (
        <EmptyState
          icon={Radio}
          title="No providers found"
          description={
            filter !== "all"
              ? `No ${filter} providers available yet. Try a different filter.`
              : "No signal providers are listed yet. Check back soon."
          }
        />
      )}

      {/* Provider grid */}
      {!isLoading && providers && providers.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
      <p className="mt-8 text-center text-[10px] text-muted-foreground/60">
        Past performance is not indicative of future results. Statistics
        computed by Sage Intelligence based on historical signal data.
      </p>

      {/* Subscribe consent sheet */}
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
