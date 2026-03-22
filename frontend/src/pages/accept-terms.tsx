import { useState } from "react";
import { Link } from "react-router-dom";
import { AuthLayout } from "@/components/layout/auth-layout";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/contexts/auth-context";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "sonner";

export function AcceptTermsPage() {
  usePageTitle("Accept Terms");
  useAuth();
  const [accepted, setAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAccept() {
    setLoading(true);
    setError(null);
    try {
      await apiFetch("/auth/accept-terms", {
        method: "POST",
        body: JSON.stringify({
          tos_accepted: true,
          privacy_accepted: true,
          risk_waiver_accepted: true,
        }),
      });
      toast.success("Terms accepted");
      window.location.href = "/";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to accept terms");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout>
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground text-center">
          Welcome! Please accept our terms to continue.
        </p>

        {error && (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <label className="flex items-start gap-3 cursor-pointer">
          <Checkbox
            checked={accepted}
            onCheckedChange={(v) => setAccepted(v === true)}
            disabled={loading}
          />
          <span className="text-sm text-muted-foreground leading-snug">
            I agree to the{" "}
            <Link to="/terms" target="_blank" className="text-primary hover:underline">
              Terms of Service
            </Link>{" "}
            and{" "}
            <Link to="/privacy" target="_blank" className="text-primary hover:underline">
              Privacy Policy
            </Link>
          </span>
        </label>

        <Button
          className="w-full"
          disabled={!accepted || loading}
          onClick={handleAccept}
        >
          {loading ? "Saving..." : "Continue"}
        </Button>
      </div>
    </AuthLayout>
  );
}

export default AcceptTermsPage;
