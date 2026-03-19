import { useEffect, useState } from "react";

/**
 * Thin animated progress bar at the top of the page.
 * Rendered inside Suspense fallback, so it only shows during lazy chunk loading.
 * Has a 200ms delay to prevent flash on fast loads.
 */
export function NavigationProgress() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setShow(true), 200);
    return () => clearTimeout(timer);
  }, []);

  if (!show) return null;

  return (
    <div className="fixed inset-x-0 top-0 z-[100] h-0.5 overflow-hidden bg-primary/20">
      <div className="h-full w-1/3 animate-[progress_1.5s_ease-in-out_infinite] rounded-full bg-primary" />
    </div>
  );
}
