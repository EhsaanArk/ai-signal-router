import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSendCode, useVerifyCode } from "@/hooks/use-telegram";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

type Step = "phone" | "code" | "2fa";

const STEP_LABELS: Record<Step, { num: number; label: string }> = {
  phone: { num: 1, label: "Phone number" },
  code: { num: 2, label: "Verification code" },
  "2fa": { num: 3, label: "Two-factor auth" },
};

interface TelegramConnectFormProps {
  onSuccess?: () => void;
  defaultPhone?: string;
}

export function TelegramConnectForm({ onSuccess, defaultPhone }: TelegramConnectFormProps = {}) {
  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState(defaultPhone ?? "");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [phoneCodeHash, setPhoneCodeHash] = useState("");
  const [resendCooldown, setResendCooldown] = useState(0);

  const sendCode = useSendCode();

  // Cooldown timer
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => {
      setResendCooldown((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);
  const verifyCode = useVerifyCode();

  const stepInfo = STEP_LABELS[step];

  async function handleSendCode(e: React.FormEvent) {
    e.preventDefault();
    const normalized = phone.replace(/[\s\-()]/g, "");
    const phoneRegex = /^\+\d{7,15}$/;
    if (!phoneRegex.test(normalized)) {
      toast.error("Enter a valid phone number with country code (e.g., +1234567890)");
      return;
    }
    try {
      const res = await sendCode.mutateAsync(normalized);
      setPhoneCodeHash(res.phone_code_hash);
      setStep("code");
      setResendCooldown(60);
      toast.success("Verification code sent");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to send code"
      );
    }
  }

  const handleResendCode = useCallback(async () => {
    try {
      const res = await sendCode.mutateAsync(phone.replace(/[\s\-()]/g, ""));
      setPhoneCodeHash(res.phone_code_hash);
      setResendCooldown(60);
      toast.success("New verification code sent");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to resend code");
    }
  }, [phone, sendCode]);

  async function handleVerifyCode(e: React.FormEvent) {
    e.preventDefault();
    try {
      const res = await verifyCode.mutateAsync({
        phone_number: phone.replace(/[\s\-()]/g, ""),
        code,
        phone_code_hash: phoneCodeHash,
      });
      if (res.requires_2fa) {
        setStep("2fa");
        toast.info("Two-factor authentication required");
        return;
      }
      toast.success("Telegram connected successfully");
      onSuccess?.();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Verification failed"
      );
    }
  }

  async function handleSubmit2FA(e: React.FormEvent) {
    e.preventDefault();
    try {
      const res = await verifyCode.mutateAsync({
        phone_number: phone.replace(/[\s\-()]/g, ""),
        code,
        phone_code_hash: phoneCodeHash,
        password,
      });
      if (res.requires_2fa) {
        toast.error("Incorrect password, try again");
        return;
      }
      toast.success("Telegram connected successfully");
      onSuccess?.();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "2FA verification failed"
      );
    }
  }

  return (
    <div className="space-y-4">
      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {(["phone", "code", "2fa"] as Step[]).map((s, i) => {
          const info = STEP_LABELS[s];
          const isActive = s === step;
          const isDone = info.num < stepInfo.num;
          return (
            <div key={s} className="flex items-center gap-2 flex-1 last:flex-none">
              <div className={cn(
                "flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-medium",
                isDone || isActive
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              )}>
                {info.num}
              </div>
              {i < 2 && (
                <div className={cn("flex-1 h-px", isDone ? "bg-primary" : "bg-border")} />
              )}
            </div>
          );
        })}
      </div>
      <p className="text-[10px] text-muted-foreground">
        Step {stepInfo.num}: {stepInfo.label}
      </p>

      {step === "phone" && (
        <form onSubmit={handleSendCode} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="phone" className="text-xs">Phone Number</Label>
            <Input
              id="phone"
              type="tel"
              placeholder="+1234567890"
              value={phone}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPhone(e.target.value)}
              required
              className="h-8 text-sm"
            />
            <p className="text-[10px] text-muted-foreground">
              Enter the phone number linked to your personal Telegram account, including country code (e.g., +1 for US)
            </p>
          </div>
          <Button type="submit" size="sm" className="h-7 text-xs" disabled={sendCode.isPending}>
            {sendCode.isPending ? "Sending..." : "Send Code"}
          </Button>
        </form>
      )}

      {step === "code" && (
        <form onSubmit={handleVerifyCode} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="code" className="text-xs">Verification Code</Label>
            <Input
              id="code"
              type="text"
              placeholder="12345"
              value={code}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCode(e.target.value)}
              required
              className="h-8 text-sm font-mono tracking-widest"
            />
            <p className="text-[10px] text-muted-foreground">
              Check your Telegram app for the code.
            </p>
          </div>
          <p className="text-[10px] text-muted-foreground">
            Didn't receive it?{" "}
            {resendCooldown > 0 ? (
              <span className="text-muted-foreground/60">Resend code in {resendCooldown}s</span>
            ) : (
              <button
                type="button"
                className="text-primary hover:underline"
                onClick={handleResendCode}
                disabled={sendCode.isPending}
              >
                {sendCode.isPending ? "Sending..." : "Resend code"}
              </button>
            )}
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              onClick={() => { setStep("phone"); setCode(""); }}
            >
              Back
            </Button>
            <Button type="submit" size="sm" className="h-7 text-xs" disabled={verifyCode.isPending}>
              {verifyCode.isPending ? "Verifying..." : "Verify"}
            </Button>
          </div>
        </form>
      )}

      {step === "2fa" && (
        <form onSubmit={handleSubmit2FA} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="password" className="text-xs">Cloud Password</Label>
            <Input
              id="password"
              type="password"
              placeholder="Your Telegram cloud password"
              value={password}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
              required
              className="h-8 text-sm"
            />
            <p className="text-[10px] text-muted-foreground">
              The password set in Telegram's privacy settings.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              onClick={() => setStep("code")}
            >
              Back
            </Button>
            <Button type="submit" size="sm" className="h-7 text-xs" disabled={verifyCode.isPending}>
              {verifyCode.isPending ? "Verifying..." : "Verify"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
