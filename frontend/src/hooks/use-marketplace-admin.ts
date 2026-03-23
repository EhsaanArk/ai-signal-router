import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MarketplaceProvider {
  id: string;
  name: string;
  description: string | null;
  asset_class: "forex" | "crypto" | "indices" | "commodities";
  telegram_channel_id: string;
  status: "active" | "inactive" | "pending";
  subscriber_count: number;
  win_rate: number | null;
  created_at: string;
  updated_at: string | null;
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
  asset_class: "forex" | "crypto" | "indices" | "commodities";
  telegram_channel_id: string;
}

export interface UpdateProviderRequest {
  name?: string;
  description?: string;
  asset_class?: "forex" | "crypto" | "indices" | "commodities";
  telegram_channel_id?: string;
  status?: "active" | "inactive" | "pending";
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useAdminProviders() {
  return useQuery({
    queryKey: ["admin-marketplace-providers"],
    queryFn: () =>
      apiFetch<MarketplaceProvider[]>("/admin/marketplace/providers"),
  });
}

export function useAdminMarketplaceStats() {
  return useQuery({
    queryKey: ["admin-marketplace-stats"],
    queryFn: () => apiFetch<MarketplaceStats>("/admin/marketplace/stats"),
    staleTime: 30_000,
  });
}

export function useCreateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateProviderRequest) =>
      apiFetch<MarketplaceProvider>("/admin/marketplace/providers", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["admin-marketplace-providers"],
      });
      queryClient.invalidateQueries({
        queryKey: ["admin-marketplace-stats"],
      });
    },
  });
}

export function useUpdateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: UpdateProviderRequest;
    }) =>
      apiFetch<MarketplaceProvider>(`/admin/marketplace/providers/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["admin-marketplace-providers"],
      });
      queryClient.invalidateQueries({
        queryKey: ["admin-marketplace-stats"],
      });
    },
  });
}

export function useDeactivateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/admin/marketplace/providers/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["admin-marketplace-providers"],
      });
      queryClient.invalidateQueries({
        queryKey: ["admin-marketplace-stats"],
      });
    },
  });
}
