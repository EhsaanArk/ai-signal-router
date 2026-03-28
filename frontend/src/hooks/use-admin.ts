import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  PaginatedAdminUsers,
  AdminUserDetail,
  AdminUserSummary,
  PaginatedAdminSignals,
  AdminSignalStats,
  AdminHealthStats,
  GlobalSetting,
} from "@/types/api";

export function useAdminUsers(limit = 50, offset = 0, search?: string) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (search) params.set("search", search);

  return useQuery({
    queryKey: ["admin-users", limit, offset, search],
    queryFn: () => apiFetch<PaginatedAdminUsers>(`/admin/users?${params}`),
  });
}

export function useAdminUserDetail(userId: string) {
  return useQuery({
    queryKey: ["admin-user", userId],
    queryFn: () => apiFetch<AdminUserDetail>(`/admin/users/${userId}`),
    enabled: !!userId,
  });
}

export function useAdminUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      userId,
      data,
    }: {
      userId: string;
      data: { subscription_tier?: string; is_disabled?: boolean; disconnect_telegram?: boolean };
    }) =>
      apiFetch<AdminUserSummary>(`/admin/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-user"] });
    },
  });
}

interface SignalFilters {
  status?: string;
  date_from?: string;
  date_to?: string;
  user_email?: string;
  channel_id?: string;
}

export function useAdminSignals(
  limit = 50,
  offset = 0,
  filters: SignalFilters = {}
) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (filters.status && filters.status !== "all")
    params.set("status", filters.status);
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);
  if (filters.user_email) params.set("user_email", filters.user_email);
  if (filters.channel_id) params.set("channel_id", filters.channel_id);

  return useQuery({
    queryKey: ["admin-signals", limit, offset, filters],
    queryFn: () => apiFetch<PaginatedAdminSignals>(`/admin/signals?${params}`),
  });
}

export function useAdminSignalStats() {
  return useQuery({
    queryKey: ["admin-signal-stats"],
    queryFn: () => apiFetch<AdminSignalStats>("/admin/signals/stats"),
    staleTime: 30_000,
  });
}

export function useAdminHealth() {
  return useQuery({
    queryKey: ["admin-health"],
    queryFn: () => apiFetch<AdminHealthStats>("/admin/health"),
    staleTime: 60_000,
  });
}

export function useAdminSettings() {
  return useQuery({
    queryKey: ["admin-settings"],
    queryFn: () => apiFetch<GlobalSetting[]>("/admin/settings"),
    staleTime: 30_000,
  });
}

export function useUpdateAdminSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (settings: Record<string, string>) =>
      apiFetch<GlobalSetting[]>("/admin/settings", {
        method: "PUT",
        body: JSON.stringify({ settings }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-settings"] });
    },
  });
}
