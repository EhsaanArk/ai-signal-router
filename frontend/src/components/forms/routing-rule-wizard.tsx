import { useState } from "react";
import { StepSelectChannel } from "./step-select-channel";
import { StepSetDestination } from "./step-set-destination";
import { StepSymbolMappings } from "./step-symbol-mappings";
import { useCreateRule } from "@/hooks/use-routing-rules";
import { toast } from "sonner";
import type { RoutingRuleCreate } from "@/types/api";

interface WizardData {
  source_channel_id: string;
  source_channel_name: string;
  destination_webhook_url: string;
  payload_version: "V1" | "V2";
  symbol_mappings: Record<string, string>;
}

const STEPS = ["Select Channel", "Set Destination", "Symbol Mappings"] as const;

interface Props {
  onComplete: () => void;
}

export function RoutingRuleWizard({ onComplete }: Props) {
  const [step, setStep] = useState(0);
  const [data, setData] = useState<Partial<WizardData>>({});
  const createRule = useCreateRule();

  function handleNext(partial: Partial<WizardData>) {
    setData((prev) => ({ ...prev, ...partial }));
    setStep((s) => s + 1);
  }

  async function handleFinish(mappings: Record<string, string>) {
    const payload: RoutingRuleCreate = {
      source_channel_id: data.source_channel_id!,
      source_channel_name: data.source_channel_name,
      destination_webhook_url: data.destination_webhook_url!,
      payload_version: data.payload_version || "V1",
      symbol_mappings: mappings,
      risk_overrides: {},
    };

    try {
      await createRule.mutateAsync(payload);
      toast.success("Routing rule created");
      onComplete();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to create rule"
      );
    }
  }

  return (
    <div className="space-y-6">
      {/* Step indicator */}
      <div className="flex gap-2">
        {STEPS.map((label, i) => (
          <div
            key={label}
            className={`flex-1 rounded-full h-1.5 ${
              i <= step ? "bg-primary" : "bg-muted"
            }`}
          />
        ))}
      </div>
      <p className="text-sm text-muted-foreground">
        Step {step + 1} of {STEPS.length}: {STEPS[step]}
      </p>

      {step === 0 && (
        <StepSelectChannel
          onNext={(channelId, channelName) =>
            handleNext({
              source_channel_id: channelId,
              source_channel_name: channelName,
            })
          }
        />
      )}
      {step === 1 && (
        <StepSetDestination
          onNext={(url, version) =>
            handleNext({
              destination_webhook_url: url,
              payload_version: version,
            })
          }
          onBack={() => setStep(0)}
        />
      )}
      {step === 2 && (
        <StepSymbolMappings
          onFinish={handleFinish}
          onBack={() => setStep(1)}
          isSubmitting={createRule.isPending}
        />
      )}
    </div>
  );
}
