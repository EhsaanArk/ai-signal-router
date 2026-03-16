import { Loader2 } from "lucide-react";

export function LoadingSpinner() {
  return (
    <div className="flex h-screen flex-col items-center justify-center gap-3 bg-background">
      <img src="/logo.svg" alt="" className="h-10 w-10 animate-pulse" />
      <p className="text-xs text-muted-foreground">Loading...</p>
    </div>
  );
}

export function PageLoader() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
    </div>
  );
}
