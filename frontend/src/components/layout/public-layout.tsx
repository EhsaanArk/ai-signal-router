import { Suspense } from "react";
import { Link, Outlet } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { PageLoader } from "@/components/shared/loading-spinner";

export function PublicLayout() {
  const { user } = useAuth();

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      {/* Top bar */}
      <header className="flex h-14 items-center justify-between border-b border-border px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-2">
          <img src="/logo.svg" alt="Sage Radar AI" className="h-7 w-7" />
          <span className="text-sm font-semibold tracking-tight">
            Sage Radar AI
          </span>
          <span className="text-[7px] font-bold uppercase tracking-wider px-1 py-px rounded-full bg-amber-500/15 text-amber-500 border border-amber-500/20">
            Beta
          </span>
        </Link>

        <div className="flex items-center gap-3">
          {user ? (
            <Link
              to="/"
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {user.email}
            </Link>
          ) : (
            <Link
              to="/login"
              className="text-xs font-medium text-primary hover:text-primary/80 transition-colors"
            >
              Sign In
            </Link>
          )}
        </div>
      </header>

      {/* Body */}
      <main className="flex-1">
        <Suspense fallback={<PageLoader />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
}

export default PublicLayout;
