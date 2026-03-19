import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import * as Sentry from "@sentry/react";

declare global {
  interface Window {
    __BUILD_TIME__?: number;
  }
}

const THROTTLE_MS = 30_000; // 30 seconds

export function useVersionCheck() {
  const location = useLocation();
  const lastCheckRef = useRef(0);
  const [stale, setStale] = useState(false);

  useEffect(() => {
    const now = Date.now();
    if (now - lastCheckRef.current < THROTTLE_MS) return;
    lastCheckRef.current = now;

    const currentBuild = window.__BUILD_TIME__;
    if (!currentBuild) return;

    fetch(`/version.json?t=${now}`)
      .then((res) => {
        if (!res.ok) return null;
        return res.json() as Promise<{ buildTime: number }>;
      })
      .then((data) => {
        if (!data) return;
        if (data.buildTime !== currentBuild) {
          setStale(true);
          Sentry.addBreadcrumb({
            category: "version",
            message: `Stale version detected: running=${currentBuild}, latest=${data.buildTime}`,
            level: "warning",
          });
        }
      })
      .catch(() => {
        // Fetch failed (offline, 404, etc.) — silently ignore
      });
  }, [location.pathname]);

  return { stale };
}
