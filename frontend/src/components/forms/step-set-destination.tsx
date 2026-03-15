import { useState, useCallback, useMemo } from "react";
import { CheckCircle2, Lightbulb, Loader2, Pencil, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { TemplateBuilder } from "./template-builder";
import { apiFetch } from "@/lib/api";
import { cn, extractAccountIdFromUrl, extractTemplateMetadata } from "@/lib/utils";
import { useRoutingRules } from "@/hooks/use-routing-rules";
import type { DestinationType, RoutingRuleResponse, TestWebhookResponse } from "@/types/api";

interface Props {
  initialData?: {
    destination_webhook_url?: string;
    payload_version?: "V1" | "V2";
    webhook_body_template?: Record<string, unknown> | null;
    destination_type?: DestinationType;
    destination_label?: string;
  };
  onNext: (
    url: string,
    version: "V1" | "V2",
    webhookBodyTemplate: Record<string, unknown> | null,
    destinationType: DestinationType,
    destinationLabel: string,
  ) => void;
  onBack: () => void;
}

const DESTINATION_TYPES: { value: DestinationType; label: string; description: string }[] = [
  { value: "sagemaster_forex", label: "SageMaster Forex", description: "Forex pairs via sfx.sagemaster.io" },
  { value: "sagemaster_crypto", label: "SageMaster Crypto", description: "Crypto pairs via api.sagemaster.io" },
  { value: "custom", label: "Custom Webhook", description: "Any webhook endpoint" },
];

function detectTemplateMismatch(
  destinationType: DestinationType,
  templateText: string
): string | null {
  if (!templateText.trim()) return null;
  try {
    const parsed = JSON.parse(templateText);
    if (destinationType === "sagemaster_forex" && "aiAssistId" in parsed) {
      return "Your template looks like a Crypto template. Did you mean to select SageMaster Crypto?";
    }
    if (destinationType === "sagemaster_crypto" && "assistId" in parsed && !("aiAssistId" in parsed)) {
      return "Your template looks like a Forex template. Did you mean to select SageMaster Forex?";
    }
  } catch {
    // Invalid JSON — will be caught by submit validation
  }
  return null;
}

export function StepSetDestination({ initialData, onNext, onBack }: Props) {
  const [url, setUrl] = useState(initialData?.destination_webhook_url ?? "");
  const [version, setVersion] = useState<"V1" | "V2">(initialData?.payload_version ?? "V1");
  const [urlError, setUrlError] = useState("");
  const initialTemplateText = initialData?.webhook_body_template
    ? JSON.stringify(initialData.webhook_body_template, null, 2)
    : "";
  const [templateText, setTemplateText] = useState(initialTemplateText);
  const [templateError, setTemplateError] = useState("");
  const [destinationType, setDestinationType] = useState<DestinationType>(initialData?.destination_type ?? "sagemaster_forex");
  // Preserved across back/next navigation; no UI input yet
  const destinationLabel = initialData?.destination_label ?? "";
  const [testStatus, setTestStatus] = useState<"idle" | "testing" | "success" | "failed">("idle");
  const [testError, setTestError] = useState("");
  const [urlLocked, setUrlLocked] = useState(() => !!extractAccountIdFromUrl(initialData?.destination_webhook_url ?? ""));
  const [templateLocked, setTemplateLocked] = useState(() => !!extractTemplateMetadata(initialTemplateText).assistId);
  const [suggestionDismissed, setSuggestionDismissed] = useState(false);

  const accountId = extractAccountIdFromUrl(url);
  const templateMeta = extractTemplateMetadata(templateText);

  // Duplicate webhook URL detection
  const { data: existingRules } = useRoutingRules();
  const matchingRules = useMemo(() => {
    if (!url || !existingRules) return [];
    return existingRules.filter(
      (r) => r.destination_webhook_url === url && r.webhook_body_template
    );
  }, [url, existingRules]);

  function applyFromRule(rule: RoutingRuleResponse) {
    setDestinationType(rule.destination_type as DestinationType);
    setVersion((rule.payload_version as "V1" | "V2") || "V1");
    if (rule.webhook_body_template) {
      const text = JSON.stringify(rule.webhook_body_template, null, 2);
      setTemplateText(text);
      const meta = extractTemplateMetadata(text);
      if (meta.assistId) setTemplateLocked(true);
    }
    if (rule.destination_type === "sagemaster_crypto") setVersion("V1");
    setSuggestionDismissed(true);
  }

  const handleUrlPaste = useCallback((e: React.ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData.getData("text");
    if (extractAccountIdFromUrl(pasted)) {
      // Let the onChange fire first, then lock on next tick
      setTimeout(() => setUrlLocked(true), 0);
    }
  }, []);

  const handleTemplateChange = useCallback((text: string) => {
    setTemplateText(text);
    if (templateError) setTemplateError("");
    // Auto-lock when valid JSON with assistId is pasted
    const meta = extractTemplateMetadata(text);
    if (meta.assistId && !templateLocked) {
      setTemplateLocked(true);
    }
  }, [templateError, templateLocked]);

  const templateWarning = detectTemplateMismatch(destinationType, templateText);

  async function handleTestWebhook() {
    try {
      new URL(url);
    } catch {
      setUrlError("Enter a valid URL first");
      return;
    }
    setTestStatus("testing");
    setTestError("");
    try {
      const result = await apiFetch<TestWebhookResponse>("/webhook/test", {
        method: "POST",
        body: JSON.stringify({ url }),
      });
      if (result.success) {
        setTestStatus("success");
      } else {
        setTestStatus("failed");
        setTestError(result.error || "Webhook test failed");
      }
    } catch (err) {
      setTestStatus("failed");
      setTestError(err instanceof Error ? err.message : "Test failed");
    }
  }

  function handleNext() {
    try {
      new URL(url);
    } catch {
      setUrlError("Enter a valid URL (e.g., https://...)");
      return;
    }
    setUrlError("");

    // Template is required for SageMaster destinations (contains assistId)
    if (
      (destinationType === "sagemaster_forex" || destinationType === "sagemaster_crypto") &&
      !templateText.trim()
    ) {
      setTemplateError(
        "Required for SageMaster destinations. Copy the JSON from your Assists overview page in SageMaster."
      );
      return;
    }

    let parsedTemplate: Record<string, unknown> | null = null;
    if (templateText.trim()) {
      try {
        parsedTemplate = JSON.parse(templateText.trim());
        if (typeof parsedTemplate !== "object" || Array.isArray(parsedTemplate)) {
          setTemplateError("Template must be a JSON object");
          return;
        }
      } catch {
        setTemplateError("Invalid JSON");
        return;
      }
    }
    setTemplateError("");

    onNext(url, version, parsedTemplate, destinationType, destinationLabel);
  }

  return (
    <div className="space-y-4">
      {/* Destination Type */}
      <div className="space-y-2">
        <Label className="text-xs">Destination Platform</Label>
        <div className="grid grid-cols-3 gap-2">
          {DESTINATION_TYPES.map((dt) => (
            <button
              key={dt.value}
              type="button"
              onClick={() => {
                setDestinationType(dt.value);
                if (dt.value === "sagemaster_crypto") setVersion("V1");
              }}
              className={cn(
                "rounded-md border px-3 py-2.5 text-left transition-colors",
                destinationType === dt.value
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-muted-foreground/30"
              )}
            >
              <p className={cn(
                "text-xs font-medium",
                destinationType === dt.value ? "text-primary" : "text-foreground"
              )}>
                {dt.label}
              </p>
              <p className="text-[10px] text-muted-foreground mt-0.5">{dt.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Webhook URL */}
      <div className="space-y-2">
        <Label htmlFor="webhook-url" className="text-xs">Webhook URL</Label>
        {urlLocked && accountId ? (
          <div className="flex items-center gap-2">
            <div className="flex-1 flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-1.5">
              <span className="text-[10px] text-muted-foreground">Account</span>
              <code className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-mono text-primary">
                {accountId}
              </code>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => setUrlLocked(false)}
            >
              <Pencil className="h-3 w-3" />
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8"
              disabled={!url || testStatus === "testing"}
              onClick={handleTestWebhook}
            >
              {testStatus === "testing" && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
              {testStatus === "success" && <CheckCircle2 className="mr-1 h-3 w-3 text-emerald-500" />}
              {testStatus === "failed" && <XCircle className="mr-1 h-3 w-3 text-rose-500" />}
              Test
            </Button>
          </div>
        ) : (
          <div className="flex gap-2">
            <Input
              id="webhook-url"
              type="url"
              placeholder="https://your-webhook-url.com/..."
              value={url}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                setUrl(e.target.value);
                if (urlError) setUrlError("");
                if (testStatus !== "idle") setTestStatus("idle");
              }}
              onPaste={handleUrlPaste}
              className="flex-1 h-8 text-sm"
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8"
              disabled={!url || testStatus === "testing"}
              onClick={handleTestWebhook}
            >
              {testStatus === "testing" && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
              {testStatus === "success" && <CheckCircle2 className="mr-1 h-3 w-3 text-emerald-500" />}
              {testStatus === "failed" && <XCircle className="mr-1 h-3 w-3 text-rose-500" />}
              Test
            </Button>
          </div>
        )}
        {urlError && (
          <p className="text-[11px] text-destructive">{urlError}</p>
        )}
        {testStatus === "success" && (
          <p className="text-[11px] text-emerald-600 dark:text-emerald-400">Webhook responded successfully</p>
        )}
        {testStatus === "failed" && testError && (
          <p className="text-[11px] text-destructive">{testError}</p>
        )}
      </div>

      {/* Duplicate webhook suggestion */}
      {matchingRules.length > 0 && !suggestionDismissed && (
        <div className="rounded-md border border-primary/30 bg-primary/5 px-3 py-2.5 space-y-2">
          <div className="flex items-start gap-2">
            <Lightbulb className="h-3.5 w-3.5 text-primary mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium">
                {matchingRules.length === 1
                  ? "You have a route using this webhook"
                  : `You have ${matchingRules.length} routes using this webhook`}
              </p>
              {matchingRules.map((rule) => (
                <div key={rule.id} className="flex items-center justify-between gap-2 mt-1.5">
                  <p className="text-[11px] text-muted-foreground truncate">
                    {rule.rule_name || rule.destination_label || "Unnamed route"}
                    <span className="ml-1 opacity-60">
                      ({DESTINATION_TYPES.find((dt) => dt.value === rule.destination_type)?.label ?? rule.destination_type}, {rule.payload_version || "V1"})
                    </span>
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-6 text-[10px] shrink-0"
                    onClick={() => applyFromRule(rule)}
                  >
                    Use Settings
                  </Button>
                </div>
              ))}
            </div>
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setSuggestionDismissed(true)}
            >
              <XCircle className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Signal Format — crypto only supports V1 */}
      <div className="space-y-2">
        <Label className="text-xs">Signal Format</Label>
        {destinationType === "sagemaster_crypto" ? (
          <p className="text-xs text-muted-foreground rounded-md border px-3 py-2">V1 only — SageMaster Crypto does not support V2 signal format.</p>
        ) : (
          <RadioGroup
            value={version}
            onValueChange={(v: string) => setVersion(v as "V1" | "V2")}
          >
            <div className="flex gap-2">
              <div className="flex items-center space-x-2 rounded-md border px-3 py-2 flex-1">
                <RadioGroupItem value="V1" id="v1" />
                <Label htmlFor="v1" className="cursor-pointer text-xs">
                  <span className="font-medium">V1</span>
                  <span className="block text-[10px] text-muted-foreground mt-0.5">Strategy trigger — sends entry, close, and breakeven commands. (No Price/TP/SL)</span>
                </Label>
              </div>
              <div className="flex items-center space-x-2 rounded-md border px-3 py-2 flex-1">
                <RadioGroupItem value="V2" id="v2" />
                <Label htmlFor="v2" className="cursor-pointer text-xs">
                  <span className="font-medium">V2</span>
                  <span className="block text-[10px] text-muted-foreground mt-0.5">Full signal — includes entry, TP, SL, and lot size</span>
                </Label>
              </div>
            </div>
          </RadioGroup>
        )}
      </div>

      {/* Template Builder */}
      {templateLocked && templateMeta.assistId ? (
        <div className="space-y-1.5">
          <Label className="text-xs">Webhook Body Template</Label>
          <div className="flex items-center gap-2">
            <div className="flex-1 flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 px-3 py-1.5">
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-muted-foreground">Assist ID</span>
                <code className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-mono text-primary">
                  {templateMeta.assistId}
                </code>
              </div>
              {templateMeta.exchange && (
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-muted-foreground">Exchange</span>
                  <code className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-mono text-primary">
                    {templateMeta.exchange}
                  </code>
                </div>
              )}
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => setTemplateLocked(false)}
            >
              <Pencil className="h-3 w-3" />
            </Button>
          </div>
        </div>
      ) : (
        <TemplateBuilder
          value={templateText}
          onChange={handleTemplateChange}
          error={templateError}
        />
      )}

      {/* Template mismatch warning */}
      {templateWarning && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2">
          <p className="text-[11px] text-amber-600 dark:text-amber-400">{templateWarning}</p>
        </div>
      )}

      <div className="flex gap-2 pt-2">
        <Button variant="outline" size="sm" onClick={onBack}>
          Back
        </Button>
        <Button size="sm" onClick={handleNext} disabled={!url}>
          Next
        </Button>
      </div>
    </div>
  );
}
