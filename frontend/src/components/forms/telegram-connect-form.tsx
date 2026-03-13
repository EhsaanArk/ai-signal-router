import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSendCode, useVerifyCode } from "@/hooks/use-telegram";
import { toast } from "sonner";

type Step = "phone" | "code" | "2fa";

export function TelegramConnectForm() {
  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [phoneCodeHash, setPhoneCodeHash] = useState("");

  const sendCode = useSendCode();
  const verifyCode = useVerifyCode();

  async function handleSendCode(e: React.FormEvent) {
    e.preventDefault();
    const phoneRegex = /^\+\d{7,15}$/;
    if (!phoneRegex.test(phone.replace(/\s/g, ""))) {
      toast.error("Enter a valid phone number with country code (e.g., +1234567890)");
      return;
    }
    try {
      const res = await sendCode.mutateAsync(phone);
      setPhoneCodeHash(res.phone_code_hash);
      setStep("code");
      toast.success("Verification code sent");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to send code"
      );
    }
  }

  async function handleVerifyCode(e: React.FormEvent) {
    e.preventDefault();
    try {
      const res = await verifyCode.mutateAsync({
        phone_number: phone,
        code,
        phone_code_hash: phoneCodeHash,
      });
      if (res.requires_2fa) {
        setStep("2fa");
        toast.info("Two-factor authentication required");
        return;
      }
      toast.success("Telegram connected successfully");
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
        phone_number: phone,
        code,
        phone_code_hash: phoneCodeHash,
        password,
      });
      if (res.requires_2fa) {
        toast.error("Incorrect password, try again");
        return;
      }
      toast.success("Telegram connected successfully");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "2FA verification failed"
      );
    }
  }

  if (step === "phone") {
    return (
      <form onSubmit={handleSendCode} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="phone">Phone Number</Label>
          <Input
            id="phone"
            type="tel"
            placeholder="+1234567890"
            value={phone}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPhone(e.target.value)}
            required
          />
          <p className="text-xs text-muted-foreground">
            Include country code (e.g., +1 for US)
          </p>
        </div>
        <Button type="submit" disabled={sendCode.isPending}>
          {sendCode.isPending ? "Sending..." : "Send Code"}
        </Button>
      </form>
    );
  }

  if (step === "2fa") {
    return (
      <form onSubmit={handleSubmit2FA} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="password">Two-Factor Password</Label>
          <Input
            id="password"
            type="password"
            placeholder="Your Telegram cloud password"
            value={password}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
            required
          />
          <p className="text-xs text-muted-foreground">
            Enter the cloud password you set in Telegram's privacy settings.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => setStep("code")}
          >
            Back
          </Button>
          <Button type="submit" disabled={verifyCode.isPending}>
            {verifyCode.isPending ? "Verifying..." : "Verify"}
          </Button>
        </div>
      </form>
    );
  }

  return (
    <form onSubmit={handleVerifyCode} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="code">Verification Code</Label>
        <Input
          id="code"
          type="text"
          placeholder="12345"
          value={code}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCode(e.target.value)}
          required
        />
        <p className="text-xs text-muted-foreground">
          Enter the code sent to your Telegram app.
        </p>
      </div>
      <div className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            setStep("phone");
            setCode("");
          }}
        >
          Back
        </Button>
        <Button type="submit" disabled={verifyCode.isPending}>
          {verifyCode.isPending ? "Verifying..." : "Verify"}
        </Button>
      </div>
    </form>
  );
}
