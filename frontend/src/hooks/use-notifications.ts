import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { NotificationPreferences, TelegramBotLinkResponse } from "@/types/api";

export function useNotificationPreferences(polling?: boolean) {
  return useQuery({
    queryKey: ["notification-preferences"],
    queryFn: () =>
      apiFetch<NotificationPreferences>("/settings/notifications"),
    refetchInterval: polling ? 3000 : false,
  });
}

export function useUpdateNotificationPreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<NotificationPreferences>) =>
      apiFetch<NotificationPreferences>("/settings/notifications", {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notification-preferences"] });
    },
  });
}

export function useTelegramBotLink() {
  return useQuery({
    queryKey: ["telegram-bot-link"],
    queryFn: () =>
      apiFetch<TelegramBotLinkResponse>("/settings/telegram-bot-link"),
    retry: false,
  });
}
