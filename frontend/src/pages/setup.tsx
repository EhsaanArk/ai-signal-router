import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Check, CheckCircle2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { TelegramConnectForm } from "@/components/forms/telegram-connect-form";
import { RoutingRuleWizard } from "@/components/forms/routing-rule-wizard";
import { useTelegramStatus } from "@/hooks/use-telegram";
import { usePageTitle } from "@/hooks/use-page-title";
import { cn } from "@/lib/utils";

const STEPS = [
  { label: "Connect Telegram", description: "Link your account" },
  { label: "Create Route", description: "Channel to destination" },
  { label: "Setup Complete", description: "You're all set" },
] as const;

function completeSetup() {
  localStorage.setItem("sgm_setup_complete", "true");
}

export function SetupPage() {
  usePageTitle("Setup");
  const navigate = useNavigate();
  const [step, setStep] = useState(0);

  const { data: telegramStatus, isLoading: tgLoading } = useTelegramStatus();

  const isConnected = telegramStatus?.connected ?? false;

  // Auto-advance step 1 if already connected
  useEffect(() => {
    if (!tgLoading && isConnected && step === 0) {
      setStep(1);
    }
  }, [tgLoading, isConnected, step]);

  function handleSkip() {
    completeSetup();
    navigate("/", { replace: true });
  }

  function handleGoToDashboard() {
    completeSetup();
    navigate("/", { replace: true });
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <div className="border-b px-6 py-4">
        <h1 className="text-lg font-semibold">Setup your Sage Radar AI</h1>
        <p className="text-sm text-muted-foreground">
          Complete these steps to start routing signals
        </p>
      </div>

      <div className="flex-1 flex flex-col items-center px-4 py-8">
        <div className="w-full max-w-2xl space-y-8">
          {/* Step indicator */}
          <div className="flex items-center gap-0">
            {STEPS.map((s, i) => (
              <div key={s.label} className="flex items-center flex-1 last:flex-none">
                <div className="flex items-center gap-2">
                  <div
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium transition-colors",
                      i < step
                        ? "bg-primary text-primary-foreground"
                        : i === step
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-muted-foreground"
                    )}
                  >
                    {i < step ? <Check className="h-4 w-4" /> : i + 1}
                  </div>
                  <div className="hidden sm:block">
                    <p className={cn(
                      "text-xs font-medium leading-none",
                      i <= step ? "text-foreground" : "text-muted-foreground"
                    )}>
                      {s.label}
                    </p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      {s.description}
                    </p>
                  </div>
                </div>
                {i < STEPS.length - 1 && (
                  <div className={cn(
                    "flex-1 h-px mx-3",
                    i < step ? "bg-primary" : "bg-border"
                  )} />
                )}
              </div>
            ))}
          </div>

          {/* Step content */}
          <Card>
            <CardContent className="pt-6">
              {/* Step 1: Connect Telegram */}
              {step === 0 && (
                <div className="space-y-4">
                  <div>
                    <h2 className="text-base font-semibold">Connect Telegram</h2>
                    <p className="text-sm text-muted-foreground">
                      Link your Telegram account to start receiving signals
                    </p>
                  </div>
                  {tgLoading ? (
                    <p className="text-sm text-muted-foreground">
                      Checking connection status...
                    </p>
                  ) : isConnected ? (
                    <div className="flex items-center gap-2 text-sm text-emerald-600">
                      <CheckCircle2 className="h-4 w-4" />
                      Already connected
                    </div>
                  ) : (
                    <TelegramConnectForm onSuccess={() => setStep(1)} />
                  )}
                </div>
              )}

              {/* Step 2: Create Route */}
              {step === 1 && (
                <div className="space-y-4">
                  <div>
                    <h2 className="text-base font-semibold">Create a Route</h2>
                    <p className="text-sm text-muted-foreground">
                      Pick a channel, set a destination webhook, and configure symbol mappings
                    </p>
                  </div>
                  <RoutingRuleWizard onComplete={() => setStep(2)} />
                </div>
              )}

              {/* Step 3: Setup Complete */}
              {step === 2 && (
                <div className="flex flex-col items-center py-8 space-y-4">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-950">
                    <CheckCircle2 className="h-8 w-8 text-emerald-600" />
                  </div>
                  <h2 className="text-xl font-semibold">You're all set!</h2>
                  <p className="text-sm text-muted-foreground text-center max-w-sm">
                    Your route is active. Signals from your channel will be
                    automatically detected, parsed, and routed to your destination.
                  </p>
                  <Button onClick={handleGoToDashboard} className="mt-4">
                    Go to Dashboard
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Skip link */}
          <div className="text-center">
            <button
              onClick={handleSkip}
              className="text-xs text-muted-foreground hover:text-foreground underline transition-colors"
            >
              Skip setup
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
