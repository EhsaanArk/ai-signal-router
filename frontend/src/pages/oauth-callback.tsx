import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { BETA_DISABLED_MSG } from "@/lib/constants";

/**
 * Handles OAuth callback from Supabase (Google sign-in).
 * With implicit flow, Supabase redirects here with #access_token in the hash.
 * The Supabase client auto-processes the hash via detectSessionInUrl.
 * This page waits for the auth context to settle, then redirects.
 */
export function OAuthCallbackPage() {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Check for error in URL params
    const params = new URLSearchParams(window.location.search);
    const errorParam = params.get("error_description");
    if (errorParam) {
      setError(/banned/i.test(errorParam) ? BETA_DISABLED_MSG : errorParam);
    }
  }, []);

  // Redirect once auth settles
  useEffect(() => {
    if (error || isLoading) return;

    const timer = setTimeout(() => {
      if (user) {
        navigate("/", { replace: true });
      } else {
        // Wait a bit more for Supabase to process the hash
        setTimeout(() => {
          navigate(user ? "/" : "/login", { replace: true });
        }, 2000);
      }
    }, 1500);

    return () => clearTimeout(timer);
  }, [user, isLoading, error, navigate]);

  if (error) {
    return (
      <div className="dark flex min-h-screen items-center justify-center bg-background p-4">
        <div className="text-center space-y-4">
          <p className="text-sm text-destructive">
            {error === BETA_DISABLED_MSG ? "Account Disabled" : "Authentication failed"}
          </p>
          <p className="text-xs text-muted-foreground">{error}</p>
          <button
            onClick={() => navigate("/login", { replace: true })}
            className="text-sm text-primary hover:underline"
          >
            Back to Sign In
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="dark flex min-h-screen flex-col items-center justify-center bg-background p-4 gap-4">
      <LoadingSpinner />
      <p className="text-xs text-muted-foreground">Signing you in...</p>
    </div>
  );
}

export default OAuthCallbackPage;
