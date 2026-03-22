import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface ParsePreviewResult {
  is_valid_signal: boolean;
  action: string | null;
  symbol: string | null;
  direction: string | null;
  order_type: string | null;
  entry_price: number | null;
  stop_loss: number | null;
  take_profits: number[];
  percentage: number | null;
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
