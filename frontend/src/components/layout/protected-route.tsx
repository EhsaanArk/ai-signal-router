import { Suspense, useEffect, useState } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { removeToken } from "@/lib/auth";
import { LoadingSpinner } from "@/components/shared/loading-spinner";

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

  return <Suspense fallback={<LoadingSpinner />}><Outlet /></Suspense>;
}
