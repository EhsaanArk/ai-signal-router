import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MarketplaceProvider {
  id: string;
  name: string;
  description: string | null;
  asset_class: "forex" | "crypto" | "both";
  telegram_channel_id: string;
  is_active: boolean;
  subscriber_count: number;
  win_rate: number | null;
  total_pnl_pips: number | null;
  max_drawdown_pips: number | null;
  signal_count: number;
  track_record_days: number;
  stats_last_computed_at: string | null;
  created_at: string;
}

export interface MarketplaceStats {
  total_providers: number;
  active_providers: number;
  total_subscribers: number;
  marketplace_signals_today: number;
}

export interface CreateProviderRequest {
  name: string;
  description?: string;
  asset_class: "forex" | "crypto" | "both";
  telegram_channel_id: string;
}

export interface UpdateProviderRequest {
  name?: string;
  description?: string;
  asset_class?: "forex" | "crypto" | "both";
  telegram_channel_id?: string;
}

/** Marketplace admin API — no /v1 prefix */
const MARKETPLACE_API = (import.meta.env.VITE_API_BASE_URL || "") + "/api";

async function adminFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${MARKETPLACE_API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useAdminProviders() {
  return useQuery({
    queryKey: ["admin-marketplace-providers"],
    queryFn: () => adminFetch<MarketplaceProvider[]>("/admin/marketplace/providers"),
  });
}

export function useAdminMarketplaceStats() {
  return useQuery({
    queryKey: ["admin-marketplace-stats"],
    queryFn: () => adminFetch<MarketplaceStats>("/admin/marketplace/stats"),
    staleTime: 30_000,
  });
}

export function useCreateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateProviderRequest) =>
      adminFetch<MarketplaceProvider>("/admin/marketplace/providers", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-marketplace-providers"] });
      queryClient.invalidateQueries({ queryKey: ["admin-marketplace-stats"] });
    },
  });
}

export function useUpdateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateProviderRequest }) =>
      adminFetch<MarketplaceProvider>(`/admin/marketplace/providers/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-marketplace-providers"] });
      queryClient.invalidateQueries({ queryKey: ["admin-marketplace-stats"] });
    },
  });
}

export function useDeactivateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      adminFetch<void>(`/admin/marketplace/providers/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-marketplace-providers"] });
      queryClient.invalidateQueries({ queryKey: ["admin-marketplace-stats"] });
    },
  });
}
