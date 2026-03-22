import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AuthLayout } from "@/components/layout/auth-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

export function VerifyEmailPage() {
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");

  useEffect(() => {
    const timer = setTimeout(() => {
      const hash = window.location.hash;
      if (hash && hash.includes("access_token")) {
        setStatus("success");
      } else {
        const params = new URLSearchParams(window.location.search);
        const error = params.get("error_description");
        if (error) {
          setStatus("error");
        } else {
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
