import { Suspense, useEffect, useState } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { removeToken } from "@/lib/auth";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { StagingRedirect, isStagingEnvironment } from "@/components/shared/staging-redirect";

export function ProtectedRoute() {
  const { user, isLoading, token } = useAuth();
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    if (!isLoading) return;
    const id = setTimeout(() => setTimedOut(true), 10_000);
    return () => clearTimeout(id);
  }, [isLoading]);

  if (timedOut) {
    removeToken();
    return <Navigate to="/login" replace />;
  }

  if (isLoading) return <LoadingSpinner />;
  if (!token || !user) return <Navigate to="/login" replace />;

  // Non-admin users on staging see a redirect to production
  if (isStagingEnvironment() && !user.is_admin) {
    return <StagingRedirect />;
  }

  return <Suspense fallback={<LoadingSpinner />}><Outlet /></Suspense>;
}
