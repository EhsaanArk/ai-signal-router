import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  MarketplaceProvider,
  MarketplaceSubscription,
  MarketplaceSort,
  MarketplaceFilter,
} from "@/types/marketplace";
import { API_BASE_URL } from "@/lib/constants";

/**
 * Fetch marketplace providers — public endpoint, no auth required.
 * Uses raw fetch instead of apiFetch to avoid auth header injection.
 */
export function useMarketplaceProviders(
  sort: MarketplaceSort = "win_rate",
  filter: MarketplaceFilter = "all",
) {
  return useQuery({
    queryKey: ["marketplace-providers", sort, filter],
    queryFn: async () => {
      const params = new URLSearchParams({ sort, filter });
      const res = await fetch(
        `${API_BASE_URL}/marketplace/providers?${params}`,
        { headers: { "Content-Type": "application/json" } },
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Request failed: ${res.status}`);
      }
      return res.json() as Promise<MarketplaceProvider[]>;
    },
  });
}

/**
 * Subscribe to a marketplace provider — requires auth.
 */
export function useSubscribe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (providerId: string) =>
      apiFetch<MarketplaceSubscription>("/marketplace/subscribe", {
        method: "POST",
        body: JSON.stringify({ provider_id: providerId }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["marketplace-subscriptions"] });
      queryClient.invalidateQueries({ queryKey: ["marketplace-providers"] });
    },
  });
}

/**
 * Unsubscribe from a marketplace provider — requires auth.
 */
export function useUnsubscribe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (providerId: string) =>
      apiFetch<void>(`/marketplace/subscribe/${providerId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["marketplace-subscriptions"] });
      queryClient.invalidateQueries({ queryKey: ["marketplace-providers"] });
    },
  });
}

/**
 * Fetch current user's subscriptions — requires auth.
 */
export function useMySubscriptions(enabled = true) {
  return useQuery({
    queryKey: ["marketplace-subscriptions"],
    queryFn: () =>
      apiFetch<MarketplaceSubscription[]>("/marketplace/my-subscriptions"),
    enabled,
  });
}
