import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { LogStatsResponse, PaginatedLogs } from "@/types/api";

export function useLogs(
  limit: number = 50,
  offset: number = 0,
  status?: string,
  ruleId?: string,
) {
  const statusParam = status && status !== "all" ? `&status=${status}` : "";
  const ruleParam = ruleId ? `&rule_id=${ruleId}` : "";
  return useQuery({
    queryKey: ["logs", limit, offset, status, ruleId],
    queryFn: () =>
      apiFetch<PaginatedLogs>(
        `/logs?limit=${limit}&offset=${offset}${statusParam}${ruleParam}`,
      ),
    refetchInterval: false,
  });
}

export function useRecentLogs(limit: number = 5) {
  return useQuery({
    queryKey: ["logs", limit, 0],
    queryFn: () => apiFetch<PaginatedLogs>(`/logs?limit=${limit}&offset=0`),
    refetchInterval: 10000,
    refetchIntervalInBackground: false,
  });
}

export function useLogStats() {
  return useQuery({
    queryKey: ["log-stats"],
    queryFn: () => apiFetch<LogStatsResponse>("/logs/stats"),
    refetchInterval: 10000,
    refetchIntervalInBackground: false,
  });
}
