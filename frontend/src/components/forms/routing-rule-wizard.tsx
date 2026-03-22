import { useState, useMemo } from "react";
import { Check } from "lucide-react";
import { StepSelectChannel } from "./step-select-channel";
import { StepSetDestination } from "./step-set-destination";
import { StepActions } from "./step-actions";
import { StepSymbolMappings } from "./step-symbol-mappings";
import { TierLimitBanner } from "@/components/shared/tier-gate";
import { useCreateRule } from "@/hooks/use-routing-rules";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import type { DestinationType, RoutingRuleCreate } from "@/types/api";
import type { MoneyManagementMode } from "./template-builder";

interface WizardData {
  source_channel_id: string;
  source_channel_name: string;
  destination_webhook_url: string;
  payload_version: "V1" | "V2";
  webhook_body_template: Record<string, unknown> | null;
  risk_overrides: Record<string, unknown>;
  symbol_mappings: Record<string, string>;
  rule_name: string;
  destination_label: string;
  destination_type: DestinationType;
  enabled_actions: string[];
  keyword_blacklist: string[];
  money_management_mode?: MoneyManagementMode;
}

interface StepDef {
  id: "channel" | "destination" | "actions" | "mappings";
  label: string;
  description: string;
}

const ALL_STEPS: StepDef[] = [
  { id: "channel", label: "Channel", description: "Signal channel" },
  { id: "destination", label: "Destination", description: "Webhook + template" },
  { id: "actions", label: "Commands", description: "Commands & testing" },
  { id: "mappings", label: "Mappings", description: "Symbol maps" },
];

interface Props {
  onComplete: () => void;
}

export function RoutingRuleWizard({ onComplete }: Props) {
  const [step, setStep] = useState(0);
  const [data, setData] = useState<Partial<WizardData>>({});
  const createRule = useCreateRule();

  const activeSteps = useMemo(() => {
    if (data.destination_type === "custom") return ALL_STEPS;
    // SageMaster destinations skip the mappings step
    return ALL_STEPS.filter((s) => s.id !== "mappings");
  }, [data.destination_type]);

  const currentStepId = activeSteps[step]?.id;

  function handleNext(partial: Partial<WizardData>) {
    setData((prev) => ({ ...prev, ...partial }));
    setStep((s) => s + 1);
  }

  function handleBack(partial: Partial<WizardData>) {
    setData((prev) => ({ ...prev, ...partial }));
    setStep((s) => s - 1);
  }

  async function handleFinish(mappings: Record<string, string>) {
    const finalRiskOverrides = { ...(data.risk_overrides || {}) };
    if (data.money_management_mode && data.money_management_mode !== "unsure") {
      finalRiskOverrides.money_management_mode = data.money_management_mode;
    }
    const payload: RoutingRuleCreate = {
      source_channel_id: data.source_channel_id!,
      source_channel_name: data.source_channel_name,
      destination_webhook_url: data.destination_webhook_url!,
      payload_version: data.payload_version || "V1",
      symbol_mappings: mappings,
      risk_overrides: finalRiskOverrides,
      webhook_body_template: data.webhook_body_template ?? null,
      rule_name: data.rule_name || null,
      destination_label: null,
      destination_type: data.destination_type || "sagemaster_forex",
      enabled_actions: data.enabled_actions || null,
      keyword_blacklist: data.keyword_blacklist || [],
    };

    try {
      await createRule.mutateAsync(payload);
      toast.success("Route created");
      onComplete();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to create rule"
      );
    }
  }

  // Called when Actions step is the final step (SageMaster path).
  // Uses setData callback to read the latest state (avoids stale closure).
  async function handleActionsFinish(enabledActions: string[], riskOverrides: Record<string, unknown>, keywordBlacklist: string[]) {
    // Merge MM mode into risk_overrides if set
    const finalRiskOverrides = { ...riskOverrides };

    // Read latest wizard data via ref-stable callback to avoid stale closure
    let payload: RoutingRuleCreate | null = null;
    setData((prev) => {
      if (prev.money_management_mode && prev.money_management_mode !== "unsure") {
        finalRiskOverrides.money_management_mode = prev.money_management_mode;
      }
      payload = {
        source_channel_id: prev.source_channel_id!,
        source_channel_name: prev.source_channel_name,
        destination_webhook_url: prev.destination_webhook_url!,
        payload_version: prev.payload_version || "V1",
        symbol_mappings: {},
        risk_overrides: finalRiskOverrides,
        webhook_body_template: prev.webhook_body_template ?? null,
        rule_name: prev.rule_name || null,
        destination_label: prev.destination_label || null,
        destination_type: prev.destination_type || "sagemaster_forex",
        enabled_actions: enabledActions,
        keyword_blacklist: keywordBlacklist,
      };
      return { ...prev, enabled_actions: enabledActions, risk_overrides: finalRiskOverrides, keyword_blacklist: keywordBlacklist };
    });

    // Wait one tick for setData callback to execute
    await new Promise((r) => setTimeout(r, 0));

    if (!payload) return;

    try {
      await createRule.mutateAsync(payload);
      toast.success("Route created");
      onComplete();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to create rule"
      );
    }
  }

  const isFinalActions = currentStepId === "actions" && !activeSteps.some((s) => s.id === "mappings");

  return (
    <div className="space-y-6">
      {/* Tier limit warning */}
      <TierLimitBanner />

      {/* Step indicator — numbered circles with line */}
      <div className="flex items-center gap-0">
        {activeSteps.map((s, i) => (
          <div key={s.id} className="flex items-center flex-1 last:flex-none">
            <div className="flex items-center gap-2">
              <div
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium transition-colors",
                  i < step
                    ? "bg-primary text-primary-foreground"
                    : i === step
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground"
                )}
              >
                {i < step ? <Check className="h-3.5 w-3.5" /> : i + 1}
              </div>
              <div className="hidden sm:block">
                <p className={cn(
                  "text-xs font-medium leading-none",
                  i <= step ? "text-foreground" : "text-muted-foreground"
                )}>
                  {s.label}
                </p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{s.description}</p>
              </div>
            </div>
            {i < activeSteps.length - 1 && (
              <div className={cn(
                "flex-1 h-px mx-3",
                i < step ? "bg-primary" : "bg-border"
              )} />
            )}
          </div>
        ))}
      </div>

      {currentStepId === "channel" && (
        <StepSelectChannel
          initialData={{
            source_channel_id: data.source_channel_id,
            rule_name: data.rule_name,
          }}
          onNext={(channelId, channelName, ruleName) =>
            handleNext({
              source_channel_id: channelId,
              source_channel_name: channelName,
              rule_name: ruleName,
            })
          }
        />
      )}
      {currentStepId === "destination" && (
        <StepSetDestination
          initialData={{
            destination_webhook_url: data.destination_webhook_url,
            payload_version: data.payload_version,
            webhook_body_template: data.webhook_body_template,
            destination_type: data.destination_type,
            destination_label: data.destination_label,
            money_management_mode: data.money_management_mode,
          }}
          onNext={(url, version, webhookBodyTemplate, destinationType, destinationLabel, moneyManagementMode) =>
            handleNext({
              destination_webhook_url: url,
              payload_version: version,
              webhook_body_template: webhookBodyTemplate,
              destination_type: destinationType,
              destination_label: destinationLabel,
              money_management_mode: moneyManagementMode,
            })
          }
          onBack={(url, version, webhookBodyTemplate, destinationType, destinationLabel, moneyManagementMode) =>
            handleBack({
              destination_webhook_url: url,
              payload_version: version,
              webhook_body_template: webhookBodyTemplate,
              destination_type: destinationType,
              destination_label: destinationLabel,
              money_management_mode: moneyManagementMode,
            })
          }
        />
      )}
      {currentStepId === "actions" && (
        <StepActions
          initialData={{
            enabled_actions: data.enabled_actions,
            risk_overrides: data.risk_overrides,
            keyword_blacklist: data.keyword_blacklist,
          }}
          wizardData={data}
          onNext={(enabledActions, riskOverrides, keywordBlacklist) =>
            handleNext({
              enabled_actions: enabledActions,
              risk_overrides: riskOverrides,
              keyword_blacklist: keywordBlacklist,
            })
          }
          onBack={(enabledActions, riskOverrides, keywordBlacklist) =>
            handleBack({
              enabled_actions: enabledActions,
              risk_overrides: riskOverrides,
              keyword_blacklist: keywordBlacklist,
            })
          }
          isFinalStep={isFinalActions}
          onFinish={handleActionsFinish}
          isSubmitting={createRule.isPending}
        />
      )}
      {currentStepId === "mappings" && (
        <StepSymbolMappings
          initialData={{
            symbol_mappings: data.symbol_mappings,
          }}
          onFinish={handleFinish}
          onBack={(mappings) =>
            handleBack({ symbol_mappings: mappings })
          }
          isSubmitting={createRule.isPending}
        />
      )}
    </div>
  );
}
