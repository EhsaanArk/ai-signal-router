import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  ParserConfigResponse,
  PaginatedParserHistory,
  TestParseRequest,
  TestParseResponse,
  ReplayResponse,
  TestDispatchRequest,
  TestDispatchResponse,
} from "@/types/api";

export function useParserPrompt() {
  return useQuery({
    queryKey: ["parser-prompt"],
    queryFn: () => apiFetch<ParserConfigResponse>("/admin/parser/prompt"),
  });
}

export function useParserPromptHistory(limit = 20, offset = 0) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));

  return useQuery({
    queryKey: ["parser-prompt-history", limit, offset],
    queryFn: () =>
      apiFetch<PaginatedParserHistory>(
        `/admin/parser/prompt/history?${params}`
      ),
  });
}

export function useUpdateParserPrompt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { system_prompt: string; change_note?: string }) =>
      apiFetch<ParserConfigResponse>("/admin/parser/prompt", {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["parser-prompt"] });
      queryClient.invalidateQueries({ queryKey: ["parser-prompt-history"] });
    },
  });
}

export function useRevertParserPrompt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (versionId: string) =>
      apiFetch<ParserConfigResponse>(
        `/admin/parser/prompt/revert/${versionId}`,
        { method: "POST" }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["parser-prompt"] });
      queryClient.invalidateQueries({ queryKey: ["parser-prompt-history"] });
    },
  });
}

export function useParserModelConfig() {
  return useQuery({
    queryKey: ["parser-model"],
    queryFn: () => apiFetch<ParserConfigResponse>("/admin/parser/model"),
  });
}

export function useUpdateParserModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      model_name: string;
      temperature: number;
      change_note?: string;
    }) =>
      apiFetch<ParserConfigResponse>("/admin/parser/model", {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["parser-model"] });
    },
  });
}

export function useTestParse() {
  return useMutation({
    mutationFn: (data: TestParseRequest) =>
      apiFetch<TestParseResponse>("/admin/parser/test", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  });
}

export function useReplaySignal() {
  return useMutation({
    mutationFn: (signalLogId: string) =>
      apiFetch<ReplayResponse>(`/admin/parser/replay/${signalLogId}`, {
        method: "POST",
      }),
  });
}

export function useTestDispatch() {
  return useMutation({
    mutationFn: (data: TestDispatchRequest) =>
      apiFetch<TestDispatchResponse>("/admin/parser/test-dispatch", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  });
}
