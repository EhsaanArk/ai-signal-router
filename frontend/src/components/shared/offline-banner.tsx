import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";

export function OfflineBanner() {
  const [offline, setOffline] = useState(!navigator.onLine);
  const [visible, setVisible] = useState(!navigator.onLine);

  useEffect(() => {
    function handleOffline() {
      setOffline(true);
      setVisible(true);
    }
    function handleOnline() {
      setOffline(false);
      // Fade out, then unmount
      setTimeout(() => setVisible(false), 2000);
    }

    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);
    return () => {
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
    };
  }, []);

  if (!visible) return null;

  return (
    <div
      className={`mb-3 flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 transition-opacity duration-500 ${
        offline ? "opacity-100" : "opacity-0"
      }`}
    >
      <WifiOff className="h-3.5 w-3.5 shrink-0 text-amber-500" />
      <p className="text-xs text-amber-200/80">
        You appear to be offline. Some features may not work.
      </p>
    </div>
  );
}
