import { useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, Radio, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
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
  const navigate = useNavigate();
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
    if (!user) {
      toast.info("Sign in to subscribe to signal providers");
      navigate("/login");
      return;
    }
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

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6 space-y-1">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight">
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
        </p>
      </div>

      {/* Sort / Filter bar */}
      <div className="mb-5">
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
            <Card key={i} className="p-5">
              <div className="space-y-4">
                <div className="space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div className="space-y-1 text-center">
                    <Skeleton className="h-8 w-full" />
                    <Skeleton className="mx-auto h-2 w-8" />
                  </div>
                  <div className="space-y-1 text-center">
                    <Skeleton className="h-8 w-full" />
                    <Skeleton className="mx-auto h-2 w-8" />
                  </div>
                  <div className="space-y-1 text-center">
                    <Skeleton className="h-8 w-full" />
                    <Skeleton className="mx-auto h-2 w-8" />
                  </div>
                </div>
                <Skeleton className="h-1.5 w-full rounded-full" />
                <div className="flex justify-between">
                  <Skeleton className="h-3 w-20" />
                  <Skeleton className="h-3 w-24" />
                </div>
                <Skeleton className="h-8 w-full" />
              </div>
            </Card>
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
