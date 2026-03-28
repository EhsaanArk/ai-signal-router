import { useState, useEffect, useCallback } from "react";
import { useNotificationPreferences, useTelegramBotLink } from "./use-notifications";
import { toast } from "sonner";

export type BotLinkState = "idle" | "connecting" | "waiting" | "connected" | "timedOut" | "error";

const POLLING_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

export function useBotLinking() {
  const [waitingForLink, setWaitingForLink] = useState(false);
  const [justLinked, setJustLinked] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const [error, setError] = useState(false);

  const { data: prefs, isLoading } = useNotificationPreferences(waitingForLink);
  const { isLoading: botLinkLoading, refetch: refetchBotLink } = useTelegramBotLink();

  const isLinked = !!prefs?.telegram_bot_chat_id;

  // Derive state
  let state: BotLinkState = "idle";
  if (isLinked) state = "connected";
  else if (error) state = "error";
  else if (timedOut) state = "timedOut";
  else if (waitingForLink) state = "waiting";
  else if (botLinkLoading) state = "connecting";

  // Stop polling and show success when link is detected
  useEffect(() => {
    if (waitingForLink && isLinked) {
      setWaitingForLink(false);
      setJustLinked(true);
      setTimedOut(false);
      setError(false);
      toast.success("Telegram bot linked successfully!");
    }
  }, [waitingForLink, isLinked]);

  // 5-minute timeout for polling
  useEffect(() => {
    if (!waitingForLink) return;
    const timer = setTimeout(() => {
      setWaitingForLink(false);
      setTimedOut(true);
      toast.error("Link timed out. Please try again.");
    }, POLLING_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [waitingForLink]);

  const connect = useCallback(async () => {
    setError(false);
    setTimedOut(false);
    const result = await refetchBotLink();
    if (result.data?.bot_link) {
      window.open(result.data.bot_link, "_blank");
      setWaitingForLink(true);
    } else {
      setError(true);
      toast.error("Failed to generate Telegram link. Please try again.");
    }
  }, [refetchBotLink]);

  const cancel = useCallback(() => {
    setWaitingForLink(false);
    setTimedOut(false);
    setError(false);
  }, []);

  return {
    state,
    isLinked,
    isLoading,
    justLinked,
    connect,
    cancel,
    chatId: prefs?.telegram_bot_chat_id ?? null,
  };
}
