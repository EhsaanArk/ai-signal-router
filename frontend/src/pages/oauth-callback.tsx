import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { AuthLayout } from "@/components/layout/auth-layout";
import { BETA_DISABLED_MSG } from "@/lib/constants";
import { Heart } from "lucide-react";

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
  const [isBetaFarewell, setIsBetaFarewell] = useState(false);

  useEffect(() => {
    // Check for error in URL params
    const params = new URLSearchParams(window.location.search);
    const errorParam = params.get("error_description");
    if (errorParam) {
      const banned = /banned/i.test(errorParam);
      setIsBetaFarewell(banned);
      setError(banned ? BETA_DISABLED_MSG : errorParam);
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

  if (error && isBetaFarewell) {
    return (
      <AuthLayout>
        <div className="space-y-4 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Heart className="h-6 w-6 text-primary" />
          </div>
          <h2 className="text-lg font-semibold">Thank You, Beta Pioneer!</h2>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Your feedback helped shape Sage Radar AI into what it is today.
            The beta program has ended as we prepare for the official launch.
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed">
            We&apos;re working hard on something great — you&apos;ll be the first to know when we&apos;re back.
          </p>
          <div className="pt-2">
            <Link
              to="/login"
              className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Back to Sign In
            </Link>
          </div>
        </div>
      </AuthLayout>
    );
  }

  if (error) {
    return (
      <AuthLayout>
        <div className="space-y-4 text-center">
          <p className="text-sm text-destructive font-medium">Authentication failed</p>
          <p className="text-xs text-muted-foreground">{error}</p>
          <Link
            to="/login"
            className="inline-block text-sm text-primary hover:underline"
          >
            Back to Sign In
          </Link>
        </div>
      </AuthLayout>
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
