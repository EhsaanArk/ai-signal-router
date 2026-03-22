import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface ParsePreviewResult {
  is_valid_signal: boolean;
  action: string | null;
  normalized_action_key: string | null;
  display_action_label: string | null;
  symbol: string | null;
  direction: string | null;
  order_type: string | null;
  entry_price: number | null;
  stop_loss: number | null;
  take_profits: number[];
  percentage: number | null;
  route_would_forward: boolean;
  destination_supported: boolean | null;
  blocked_reason: string | null;
  ignore_reason: string | null;
}

interface ParsePreviewRequest {
  message: string;
  destination_type: string;
  enabled_actions?: string[] | null;
}

export function useParsePreview() {
  return useMutation({
    mutationFn: (data: ParsePreviewRequest) =>
      apiFetch<ParsePreviewResult>("/parse-preview", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  });
}
