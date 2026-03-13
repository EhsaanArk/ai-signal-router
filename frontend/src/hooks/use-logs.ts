import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { PaginatedLogs } from "@/types/api";

export function useLogs(limit: number = 50, offset: number = 0, status?: string) {
  const statusParam = status && status !== "all" ? `&status=${status}` : "";
  return useQuery({
    queryKey: ["logs", limit, offset, status],
    queryFn: () =>
      apiFetch<PaginatedLogs>(`/logs?limit=${limit}&offset=${offset}${statusParam}`),
    refetchInterval: 5000,
  });
}

export function useRecentLogs(limit: number = 5) {
  return useQuery({
    queryKey: ["logs", limit, 0],
    queryFn: () => apiFetch<PaginatedLogs>(`/logs?limit=${limit}&offset=0`),
    refetchInterval: 10000,
  });
}
