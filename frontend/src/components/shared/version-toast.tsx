import { useVersionCheck } from "@/hooks/use-version-check";

export function VersionToast() {
  const { stale } = useVersionCheck();

  if (!stale) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 rounded-lg border bg-background p-4 shadow-lg">
      <p className="text-sm font-medium">New version available</p>
      <button
        onClick={() => window.location.reload()}
        className="mt-2 text-sm text-primary underline"
      >
        Refresh now
      </button>
    </div>
  );
}
