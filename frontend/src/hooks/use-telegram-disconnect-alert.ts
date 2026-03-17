import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useTelegramStatus } from "./use-telegram";

/**
 * Watches for Telegram status transitions (connected → disconnected)
 * and fires a persistent toast alerting the user. Mount once in the
 * app layout so it works regardless of which page the user is on.
 */
export function useTelegramDisconnectAlert() {
  const { data: status } = useTelegramStatus();
  const navigate = useNavigate();
  const prevConnected = useRef<boolean | null>(null);

  useEffect(() => {
    if (!status) return;

    const wasConnected = prevConnected.current;
    const isConnected = status.connected;

    // Only alert on a true → false transition (not on initial load)
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

    prevConnected.current = isConnected;
  }, [status, navigate]);
}
