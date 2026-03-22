import { Suspense, useEffect, useState } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { StagingRedirect, isStagingEnvironment } from "@/components/shared/staging-redirect";

const CURRENT_TOS_VERSION = "2026-03-22"; // Must match backend CURRENT_TOS_VERSION

export function ProtectedRoute() {
  const { user, isLoading, token } = useAuth();
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    if (!isLoading) return;
    const id = setTimeout(() => setTimedOut(true), 10_000);
    return () => clearTimeout(id);
  }, [isLoading]);

  if (timedOut) {
    return <Navigate to="/login" replace />;
  }

  if (isLoading) return <LoadingSpinner />;
  if (!token || !user) return <Navigate to="/login" replace />;

  // Non-admin users on staging see a redirect to production
  if (isStagingEnvironment() && !user.is_admin) {
    return <StagingRedirect />;
  }

  // Redirect to terms acceptance if user hasn't accepted current version
  if (user.accepted_tos_version !== CURRENT_TOS_VERSION || !user.accepted_risk_waiver) {
    return <Navigate to="/accept-terms" replace />;
  }

  return <Suspense fallback={<LoadingSpinner />}><Outlet /></Suspense>;
}
