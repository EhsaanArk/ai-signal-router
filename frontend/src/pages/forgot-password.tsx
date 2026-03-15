import { useState } from "react";
import { Link } from "react-router-dom";
import { AuthLayout } from "@/components/layout/auth-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { usePageTitle } from "@/hooks/use-page-title";
import { API_BASE_URL } from "@/lib/constants";

export function ForgotPasswordPage() {
  usePageTitle("Forgot Password");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await fetch(`${API_BASE_URL}/api/v1/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      setSubmitted(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout>
      {submitted ? (
        <div className="space-y-4 text-center">
          <p className="text-sm text-muted-foreground">
            If an account exists for that email, we've sent a password reset
            link. Please check your inbox.
          </p>
          <Link to="/login" className="text-sm text-primary hover:underline">
            Back to Sign In
          </Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={loading}
            />
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Sending..." : "Send Reset Link"}
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            <Link to="/login" className="text-primary hover:underline">
              Back to Sign In
            </Link>
          </p>
        </form>
      )}
    </AuthLayout>
  );
}
