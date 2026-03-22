import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AuthLayout } from "@/components/layout/auth-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

/**
 * Supabase handles email verification via a redirect URL with a hash fragment.
 * The Supabase JS client automatically picks up the token from the URL hash
 * on page load via onAuthStateChange. This page just shows the result.
 */
export function VerifyEmailPage() {
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");

  useEffect(() => {
    // Supabase processes the hash fragment automatically.
    // Give it a moment, then check if we have a session.
    const timer = setTimeout(() => {
      // If Supabase processed the token, onAuthStateChange in auth-context
      // will have set the session. We just show success after a brief delay.
      const hash = window.location.hash;
      if (hash && hash.includes("access_token")) {
        setStatus("success");
      } else {
        // Check URL params for error
        const params = new URLSearchParams(window.location.search);
        const error = params.get("error_description");
        if (error) {
          setStatus("error");
        } else {
          // Assume success if no error — Supabase may have already processed it
          setStatus("success");
        }
      }
    }, 1500);

    return () => clearTimeout(timer);
  }, []);

  return (
    <AuthLayout>
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center pb-2">
          <CardTitle className="text-lg">Email Verification</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4 pt-2">
          {status === "loading" && (
            <>
              <Loader2 className="h-10 w-10 text-primary animate-spin" />
              <p className="text-sm text-muted-foreground">
                Verifying your email...
              </p>
            </>
          )}
          {status === "success" && (
            <>
              <CheckCircle2 className="h-10 w-10 text-emerald-500" />
              <p className="text-sm text-center">
                Your email has been verified. You can now access all features.
              </p>
              <Button asChild size="sm">
                <Link to="/">Go to Dashboard</Link>
              </Button>
            </>
          )}
          {status === "error" && (
            <>
              <XCircle className="h-10 w-10 text-destructive" />
              <p className="text-sm text-center text-muted-foreground">
                Invalid or expired verification link. Please try signing in
                and requesting a new verification email.
              </p>
              <Button asChild variant="outline" size="sm">
                <Link to="/login">Go to Login</Link>
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </AuthLayout>
  );
}

export default VerifyEmailPage;
