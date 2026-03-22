import { useState } from "react";
import { Link } from "react-router-dom";
import { Shield } from "lucide-react";
import { AuthLayout } from "@/components/layout/auth-layout";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/contexts/auth-context";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "sonner";

export function AcceptTermsPage() {
  usePageTitle("Accept Terms");
  const { user } = useAuth();
  const [tosAccepted, setTosAccepted] = useState(false);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [riskWaiverAccepted, setRiskWaiverAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allAccepted = tosAccepted && privacyAccepted && riskWaiverAccepted;

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
      // Force page reload to refresh user data
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
        <div className="flex items-center gap-2 justify-center mb-2">
          <Shield className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold">Before you continue</h2>
        </div>
        <p className="text-xs text-muted-foreground text-center">
          Welcome{user?.email ? `, ${user.email}` : ""}. Please review and accept our terms to continue.
        </p>

        {error && (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="space-y-3 pt-2">
          {/* Terms of Service */}
          <label className="flex items-start gap-3 cursor-pointer">
            <Checkbox
              checked={tosAccepted}
              onCheckedChange={(v) => setTosAccepted(v === true)}
              disabled={loading}
            />
            <span className="text-sm text-muted-foreground leading-snug">
              I have read and agree to the{" "}
              <Link to="/terms" target="_blank" className="text-primary hover:underline">
                Terms of Service
              </Link>
            </span>
          </label>

          {/* Privacy Policy */}
          <label className="flex items-start gap-3 cursor-pointer">
            <Checkbox
              checked={privacyAccepted}
              onCheckedChange={(v) => setPrivacyAccepted(v === true)}
              disabled={loading}
            />
            <span className="text-sm text-muted-foreground leading-snug">
              I have read and agree to the{" "}
              <Link to="/privacy" target="_blank" className="text-primary hover:underline">
                Privacy Policy
              </Link>
            </span>
          </label>

          {/* Risk Waiver */}
          <label className="flex items-start gap-3 cursor-pointer">
            <Checkbox
              checked={riskWaiverAccepted}
              onCheckedChange={(v) => setRiskWaiverAccepted(v === true)}
              disabled={loading}
            />
            <div className="text-sm text-muted-foreground leading-snug">
              <strong className="text-foreground">Risk Waiver:</strong> I understand that this
              Service is a message routing tool, not a trading platform. I acknowledge that:
              <ul className="list-disc pl-5 mt-1.5 space-y-1 text-xs">
                <li>AI parsing is best-effort and may produce incorrect data</li>
                <li>The Service may experience downtime, bugs, or failures</li>
                <li>I am solely responsible for any actions triggered by webhooks dispatched through this Service</li>
                <li>I accept all financial risk associated with my use of this Service</li>
              </ul>
            </div>
          </label>
        </div>

        <Button
          className="w-full mt-4"
          disabled={!allAccepted || loading}
          onClick={handleAccept}
        >
          {loading ? "Saving..." : "Accept and Continue"}
        </Button>
      </div>
    </AuthLayout>
  );
}

export default AcceptTermsPage;
