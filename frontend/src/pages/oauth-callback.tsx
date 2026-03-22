import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { LoadingSpinner } from "@/components/shared/loading-spinner";

/**
 * Handles OAuth callback from Supabase (Google sign-in).
 * Supabase redirects here with tokens in the URL hash.
 * The auth context picks them up automatically via onAuthStateChange.
 * This page just waits for the session to settle, then redirects.
 */
export function OAuthCallbackPage() {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isLoading) return;

    // Give Supabase a moment to process the hash fragment
    const timer = setTimeout(() => {
      if (user) {
        navigate("/", { replace: true });
      } else {
        navigate("/login", { replace: true });
      }
    }, 1000);

    return () => clearTimeout(timer);
  }, [user, isLoading, navigate]);

  return <LoadingSpinner />;
}

export default OAuthCallbackPage;
