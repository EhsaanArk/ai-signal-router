import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  RoutingRuleCreate,
  RoutingRuleResponse,
  RoutingRuleUpdate,
} from "@/types/api";

export function useRoutingRules(enabled = true) {
  return useQuery({
    queryKey: ["routing-rules"],
    queryFn: () => apiFetch<RoutingRuleResponse[]>("/routing-rules"),
    enabled,
  });
}

export function useCreateRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: RoutingRuleCreate) =>
      apiFetch<RoutingRuleResponse>("/routing-rules", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    retry: 1,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["routing-rules"] });
    },
  });
}

export function useUpdateRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: RoutingRuleUpdate;
    }) =>
      apiFetch<RoutingRuleResponse>(`/routing-rules/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["routing-rules"] });
      queryClient.invalidateQueries({ queryKey: ["routing-rule", variables.id] });
    },
  });
}

export function useDeleteRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/routing-rules/${id}`, { method: "DELETE" }),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["routing-rules"] });
      queryClient.removeQueries({ queryKey: ["routing-rule", id] });
    },
  });
}
