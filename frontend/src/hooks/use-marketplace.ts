import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase";
import type {
  MarketplaceProvider,
  MarketplaceSort,
  MarketplaceFilter,
} from "@/types/marketplace";

/** Base URL for marketplace API — no /v1 prefix (marketplace routes are at /api/marketplace) */
const MARKETPLACE_API_BASE = (import.meta.env.VITE_API_BASE_URL || "") + "/api";

interface ProviderListResponse {
  total: number;
  items: MarketplaceProvider[];
}

interface MySubscriptionItem {
  subscription_id: string;
  provider_id: string;
  provider_name: string;
  provider_asset_class: string;
  routing_rule_id: string | null;
  is_active: boolean;
  created_at: string;
}

interface SubscriptionResponse {
  subscription_id: string;
  provider_id: string;
  provider_name: string;
  routing_rule_id: string;
  is_active: boolean;
}

/** Get auth headers from Supabase session (same as apiFetch). */
async function getAuthHeaders(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    return { Authorization: `Bearer ${session.access_token}` };
  }
  return {};
}

/**
 * Fetch marketplace providers — public endpoint, no auth required.
 */
export function useMarketplaceProviders(
  sort: MarketplaceSort = "win_rate",
  filter: MarketplaceFilter = "all",
) {
  return useQuery({
    queryKey: ["marketplace-providers", sort, filter],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filter !== "all") {
        params.set("asset_class", filter);
      }
      const url = `${MARKETPLACE_API_BASE}/marketplace/providers${params.toString() ? "?" + params : ""}`;
      const res = await fetch(url, {
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Request failed: ${res.status}`);
      }
      const data: ProviderListResponse = await res.json();
      return data.items;
    },
  });
}

/**
 * Subscribe to a marketplace provider — requires auth.
 */
export function useSubscribe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      providerId,
      webhookDestinationId,
    }: {
      providerId: string;
      webhookDestinationId: string;
    }) => {
      const authHeaders = await getAuthHeaders();
      if (!authHeaders.Authorization) {
        throw new Error("Please sign in to subscribe");
      }
      const res = await fetch(
        `${MARKETPLACE_API_BASE}/marketplace/subscribe/${providerId}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...authHeaders,
          },
          body: JSON.stringify({
            webhook_destination_id: webhookDestinationId,
            consent: true,
          }),
        },
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Subscribe failed: ${res.status}`);
      }
      return res.json() as Promise<SubscriptionResponse>;
    },
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
    mutationFn: async (providerId: string) => {
      const authHeaders = await getAuthHeaders();
      if (!authHeaders.Authorization) {
        throw new Error("Please sign in to unsubscribe");
      }
      const res = await fetch(
        `${MARKETPLACE_API_BASE}/marketplace/unsubscribe/${providerId}`,
        {
          method: "DELETE",
          headers: authHeaders,
        },
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Unsubscribe failed: ${res.status}`);
      }
    },
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
    queryFn: async () => {
      const authHeaders = await getAuthHeaders();
      const res = await fetch(
        `${MARKETPLACE_API_BASE}/marketplace/my-subscriptions`,
        { headers: authHeaders },
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Failed to load subscriptions: ${res.status}`);
      }
      return res.json() as Promise<MySubscriptionItem[]>;
    },
    enabled,
  });
}
