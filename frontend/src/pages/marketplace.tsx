import { useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertTriangle, Radio, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { ProviderCard } from "@/components/marketplace/provider-card";
import { ProviderTable } from "@/components/marketplace/provider-table";
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
          toast.error(err instanceof Error ? err.message : "Failed to follow");
        },
      },
    );
  }

  function handleUnsubscribe(providerId: string) {
    unsubscribeMutation.mutate(providerId, {
      onSuccess: () => toast.success("Unfollowed"),
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "Failed to unfollow"),
    });
  }

  return (
    <div className="px-4 py-6 sm:px-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-base font-semibold tracking-tight">
            Signal Marketplace
          </h1>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Verified providers ranked by Sage Intelligence
            {providers && providers.length > 0 && (
              <span className="text-muted-foreground"> · {providers.length} listed</span>
            )}
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-muted-foreground hover:text-foreground"
          onClick={() => refetch()}
          aria-label="Refresh"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />
        </Button>
      </div>

      {/* Filters */}
      <div className="mb-4 pb-3 border-b border-border/30">
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
          <Button variant="ghost" size="sm" className="h-6 text-[11px] text-rose-400" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      )}

      {/* Loading skeleton — table on desktop, cards on mobile */}
      {isLoading && (
        <>
          {/* Desktop skeleton */}
          <div className="hidden md:block rounded-md border border-border/40 divide-y divide-border/30">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 px-4 py-3">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-4 w-14 ml-auto" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-4 w-10" />
                <Skeleton className="h-6 w-14 rounded" />
              </div>
            ))}
          </div>
          {/* Mobile skeleton */}
          <div className="md:hidden space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-md border border-border/40 bg-card p-3 space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <div className="flex gap-4">
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-12" />
                </div>
                <Skeleton className="h-3 w-1/2" />
              </div>
            ))}
          </div>
        </>
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

      {/* Data — table on desktop, cards on mobile */}
      {!isLoading && providers && providers.length > 0 && (
        <>
          {/* Desktop: screener table */}
          <div className="hidden md:block">
            <ProviderTable
              providers={providers}
              subscribedIds={subscribedIds}
              onSubscribe={handleSubscribeClick}
              onUnsubscribe={handleUnsubscribe}
            />
          </div>

          {/* Mobile: compact cards */}
          <div className="md:hidden space-y-2">
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
        </>
      )}

      {/* Disclaimer */}
      <p className="mt-6 text-center text-[10px] text-muted-foreground leading-relaxed">
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
