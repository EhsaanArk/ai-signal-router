import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { supabase } from "@/lib/supabase";

/**
 * Handles OAuth callback from Supabase (Google sign-in).
 * With PKCE flow, Supabase redirects here with ?code= parameter.
 * This page exchanges the code for a session, then redirects to dashboard.
 */
export function OAuthCallbackPage() {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [debug, setDebug] = useState("Processing auth callback...");

  useEffect(() => {
    const url = new URL(window.location.href);
    const code = url.searchParams.get("code");
    const errorParam = url.searchParams.get("error_description");

    console.log("[OAuthCallback] URL:", window.location.href);
    console.log("[OAuthCallback] code:", code ? "present" : "missing");
    console.log("[OAuthCallback] error:", errorParam);
    console.log("[OAuthCallback] hash:", window.location.hash ? "present" : "none");

    if (errorParam) {
      setError(errorParam);
      setDebug(`Error: ${errorParam}`);
      return;
    }

    if (code) {
      setDebug("Exchanging code for session...");
      // PKCE flow: exchange the code for a session
      supabase.auth.exchangeCodeForSession(code).then(({ data, error: exchangeError }) => {
        console.log("[OAuthCallback] exchangeCode result:", {
          hasSession: !!data?.session,
          error: exchangeError?.message,
        });
        if (exchangeError) {
          setError(exchangeError.message);
          setDebug(`Exchange error: ${exchangeError.message}`);
        } else {
          setDebug("Session established! Redirecting...");
        }
      }).catch((err) => {
        console.error("[OAuthCallback] exchangeCode exception:", err);
        setError(String(err));
        setDebug(`Exception: ${err}`);
      });
    } else if (window.location.hash.includes("access_token")) {
      // Implicit flow fallback — Supabase client handles hash automatically
      setDebug("Processing hash tokens...");
    } else {
      setDebug("No code or hash found — waiting for session...");
    }
  }, []);

  // Redirect once session is ready
  useEffect(() => {
    if (isLoading || error) return;

    const timer = setTimeout(() => {
      console.log("[OAuthCallback] redirect check: user =", user?.email, "isLoading =", isLoading);
      if (user) {
        navigate("/", { replace: true });
      } else {
        // Wait a bit more — session might still be processing
        setTimeout(() => {
          if (user) {
            navigate("/", { replace: true });
          } else {
            navigate("/login", { replace: true });
          }
        }, 3000);
      }
    }, 1500);

    return () => clearTimeout(timer);
  }, [user, isLoading, error, navigate]);

  if (error) {
    return (
      <div className="dark flex min-h-screen items-center justify-center bg-background p-4">
        <div className="text-center space-y-4">
          <p className="text-sm text-destructive">Authentication failed</p>
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
      <p className="text-xs text-muted-foreground">{debug}</p>
    </div>
  );
}

export default OAuthCallbackPage;
