import { useState } from "react";
import { AlertTriangle, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/auth-context";
import { apiFetch } from "@/lib/api";
import { toast } from "sonner";

export function EmailVerifyBanner() {
  const { user } = useAuth();
  const [dismissed, setDismissed] = useState(false);
  const [sending, setSending] = useState(false);

  if (!user || user.email_verified || dismissed) return null;

  async function handleResend() {
    setSending(true);
    try {
      await apiFetch<{ message: string }>("/auth/resend-verification", {
        method: "POST",
      });
      toast.success("Verification email sent — check your inbox");
    } catch {
      toast.error("Failed to send verification email");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex items-center gap-2 bg-amber-500/10 border border-amber-500/20 rounded-md px-3 py-2 mb-3">
      <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
      <p className="text-xs text-amber-600 dark:text-amber-400 flex-1">
        Please verify your email address.{" "}
        <button
          type="button"
          onClick={handleResend}
          disabled={sending}
          className="underline hover:no-underline font-medium inline-flex items-center gap-1"
        >
          {sending && <Loader2 className="h-3 w-3 animate-spin" />}
          Resend verification email
        </button>
      </p>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="text-amber-500/70 hover:text-amber-500 transition-colors"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
