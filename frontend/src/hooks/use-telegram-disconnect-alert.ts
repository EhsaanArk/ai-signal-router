import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useTelegramStatus } from "./use-telegram";

/**
 * Watches for Telegram status transitions (connected → disconnected)
 * and fires a persistent toast alerting the user. Mount once in the
 * app layout so it works regardless of which page the user is on.
 *
 * Also alerts on initial load if the user has a recent disconnection
 * (within 1 hour) — catches disconnects that happened while the tab
 * was closed or the user was away.
 */
export function useTelegramDisconnectAlert() {
  const { data: status } = useTelegramStatus();
  const navigate = useNavigate();
  const prevConnected = useRef<boolean | null>(null);
  const initialCheckDone = useRef(false);

  useEffect(() => {
    if (!status) return;

    const wasConnected = prevConnected.current;
    const isConnected = status.connected;

    // Live transition: connected → disconnected
    if (wasConnected === true && isConnected === false) {
      toast.warning("Telegram disconnected", {
        description: "Signal routing has stopped. Reconnect to resume.",
        action: {
          label: "Reconnect",
          onClick: () => navigate("/telegram"),
        },
        duration: Infinity,
      });
    }

    // Initial load: show alert if recently disconnected (within 1 hour)
    if (!initialCheckDone.current && wasConnected === null && !isConnected) {
      const disconnectedAt = status.disconnected_at;
      if (disconnectedAt) {
        const elapsed = Date.now() - new Date(disconnectedAt).getTime();
        if (elapsed < 60 * 60 * 1000) {
          toast.warning("Telegram is disconnected", {
            description: "Signal routing is paused. Reconnect to resume.",
            action: {
              label: "Reconnect",
              onClick: () => navigate("/telegram"),
            },
            duration: 15_000,
          });
        }
      }
      initialCheckDone.current = true;
    }

    prevConnected.current = isConnected;
  }, [status, navigate]);
}
