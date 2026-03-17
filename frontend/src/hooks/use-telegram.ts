import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  MessageResponse,
  SendCodeResponse,
  TelegramStatusResponse,
  VerifyCodeResponse,
} from "@/types/api";

export function useTelegramStatus() {
  return useQuery({
    queryKey: ["telegram-status"],
    queryFn: () => apiFetch<TelegramStatusResponse>("/telegram/status"),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}

export function useSendCode() {
  return useMutation({
    mutationFn: (phoneNumber: string) =>
      apiFetch<SendCodeResponse>("/telegram/send-code", {
        method: "POST",
        body: JSON.stringify({ phone_number: phoneNumber }),
      }),
  });
}

export function useVerifyCode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      phone_number: string;
      code: string;
      phone_code_hash: string;
      password?: string;
    }) =>
      apiFetch<VerifyCodeResponse>("/telegram/verify-code", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["telegram-status"] });
    },
  });
}

export function useDisconnectTelegram() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<MessageResponse>("/telegram/disconnect", {
        method: "POST",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["telegram-status"] });
    },
  });
}
