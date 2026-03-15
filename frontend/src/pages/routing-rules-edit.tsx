import { useState, useMemo } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { TemplateBuilder } from "@/components/forms/template-builder";
import { Textarea } from "@/components/ui/textarea";
import { ArrowRight, CheckCircle2, ChevronDown, ChevronRight, Lightbulb, Loader2, Plus, X, XCircle } from "lucide-react";
import { useRoutingRules, useUpdateRule } from "@/hooks/use-routing-rules";
import { apiFetch } from "@/lib/api";
import type { DestinationType, RoutingRuleResponse, TestWebhookResponse } from "@/types/api";
import { toast } from "sonner";
import { usePageTitle } from "@/hooks/use-page-title";
import { cn } from "@/lib/utils";
import {
  getActionsForDestination,
  getAllActionKeys,
} from "@/lib/action-definitions";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

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
  } catch { /* ignore */ }
  return null;
}

export function RoutingRulesEditPage() {
  usePageTitle("Edit Route");
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const updateRule = useUpdateRule();

  const { data: rule, isLoading } = useQuery({
    queryKey: ["routing-rule", id],
    queryFn: () => apiFetch<RoutingRuleResponse>(`/routing-rules/${id}`),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="space-y-4 max-w-xl">
        <Skeleton className="h-6 w-48" />
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (!rule) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">Rule not found.</p>
        <Button variant="outline" size="sm" onClick={() => navigate("/routing-rules")}>
          Back to Rules
        </Button>
      </div>
    );
  }

  const breadcrumbName = rule.rule_name || rule.source_channel_name || rule.source_channel_id;

  return (
    <div className="max-w-xl space-y-3">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-xs text-muted-foreground">
        <Link to="/routing-rules" className="hover:text-foreground transition-colors">
          Signal Routes
        </Link>
        <ChevronRight className="h-3 w-3" />
        <span className="truncate max-w-[150px]">{breadcrumbName}</span>
        <ChevronRight className="h-3 w-3" />
        <span className="text-foreground">Edit</span>
      </nav>

      <Card>
        <CardHeader className="pb-3 pt-4 px-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium">
              {breadcrumbName}
            </CardTitle>
          </div>
          {/* Timestamps */}
          <div className="flex gap-4 text-[10px] text-muted-foreground">
            {rule.created_at && (
              <span>Created: {new Date(rule.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span>
            )}
            {rule.updated_at && (
              <span>Modified: {new Date(rule.updated_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span>
            )}
          </div>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <EditRuleForm
            rule={rule}
            onSubmit={async (data) => {
              try {
                await updateRule.mutateAsync({ id: rule.id, data });
                toast.success("Route updated");
                navigate("/routing-rules");
              } catch (err) {
                toast.error(
                  err instanceof Error ? err.message : "Failed to update route"
                );
              }
            }}
            isSubmitting={updateRule.isPending}
            onCancel={() => navigate("/routing-rules")}
          />
        </CardContent>
      </Card>
    </div>
  );
}

interface EditRuleFormProps {
  rule: RoutingRuleResponse;
  onSubmit: (data: {
    rule_name: string | null;
    destination_label: string | null;
    destination_type: DestinationType;
    custom_ai_instructions: string | null;
    destination_webhook_url: string;
    payload_version: "V1" | "V2";
    symbol_mappings: Record<string, string>;
    risk_overrides: Record<string, unknown>;
    webhook_body_template: Record<string, unknown> | null;
    enabled_actions: string[] | null;
    keyword_blacklist: string[];
    is_active: boolean;
  }) => Promise<void>;
  isSubmitting: boolean;
  onCancel: () => void;
}

function EditRuleForm({ rule, onSubmit, isSubmitting, onCancel }: EditRuleFormProps) {
  const [ruleName, setRuleName] = useState(rule.rule_name || "");
  const [destinationLabel, setDestinationLabel] = useState(rule.destination_label || "");
  const [isActive, setIsActive] = useState(rule.is_active);
  const [url, setUrl] = useState(rule.destination_webhook_url);
  const [version, setVersion] = useState<"V1" | "V2">(
    rule.payload_version as "V1" | "V2"
  );
  const [urlError, setUrlError] = useState("");
  const [testStatus, setTestStatus] = useState<"idle" | "testing" | "success" | "failed">("idle");
  const [testError, setTestError] = useState("");
  const [templateText, setTemplateText] = useState(() =>
    rule.webhook_body_template
      ? JSON.stringify(rule.webhook_body_template, null, 2)
      : ""
  );
  const [templateError, setTemplateError] = useState("");
  const [lotSize, setLotSize] = useState(() => {
    const lots = rule.risk_overrides?.lots;
    return typeof lots === "string" ? lots : "";
  });
  const [destinationType, setDestinationType] = useState<DestinationType>(
    (rule.destination_type as DestinationType) || "sagemaster_forex"
  );
  const [customAiInstructions, setCustomAiInstructions] = useState(
    rule.custom_ai_instructions || ""
  );
  const [keywords, setKeywords] = useState<string[]>(rule.keyword_blacklist || []);
  const [keywordInput, setKeywordInput] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(
    !!rule.custom_ai_instructions || (rule.keyword_blacklist && rule.keyword_blacklist.length > 0),
  );
  const [enabledActions, setEnabledActions] = useState<Set<string>>(
    () => new Set(rule.enabled_actions || getAllActionKeys(destinationType)),
  );
  const [showActions, setShowActions] = useState(
    // Auto-expand if user has customized (not all enabled)
    () => rule.enabled_actions !== null && rule.enabled_actions.length < getAllActionKeys(destinationType).length,
  );
  const [suggestionDismissed, setSuggestionDismissed] = useState(false);
  const templateWarning = detectTemplateMismatch(destinationType, templateText);

  // Duplicate webhook URL detection — only when URL is changed from original
  const { data: existingRules } = useRoutingRules();
  const matchingRules = useMemo(() => {
    if (!url || url === rule.destination_webhook_url || !existingRules) return [];
    return existingRules.filter(
      (r) => r.destination_webhook_url === url && r.id !== rule.id && r.webhook_body_template
    );
  }, [url, rule.destination_webhook_url, rule.id, existingRules]);

  function applyFromRule(matched: RoutingRuleResponse) {
    setDestinationType(matched.destination_type as DestinationType);
    setVersion((matched.payload_version as "V1" | "V2") || "V1");
    if (matched.webhook_body_template) {
      setTemplateText(JSON.stringify(matched.webhook_body_template, null, 2));
    }
    if (matched.destination_type === "sagemaster_crypto") setVersion("V1");
    setSuggestionDismissed(true);
  }

  const [pairs, setPairs] = useState<{ from: string; to: string }[]>(() => {
    return Object.entries(rule.symbol_mappings).map(([from, to]) => ({
      from,
      to,
    }));
  });

  function addPair() {
    setPairs((prev) => [...prev, { from: "", to: "" }]);
  }

  function removePair(index: number) {
    setPairs((prev) => prev.filter((_, i) => i !== index));
  }

  function updatePair(index: number, field: "from" | "to", value: string) {
    setPairs((prev) =>
      prev.map((p, i) => (i === index ? { ...p, [field]: value } : p))
    );
  }

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

  async function handleSubmit() {
    try {
      new URL(url);
    } catch {
      setUrlError("Enter a valid URL (e.g., https://...)");
      return;
    }
    setUrlError("");

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

    const mappings: Record<string, string> = {};
    for (const pair of pairs) {
      if (pair.from && pair.to) {
        mappings[pair.from] = pair.to;
      }
    }

    const riskOverrides: Record<string, unknown> = {};
    if (lotSize.trim()) {
      riskOverrides.lots = lotSize.trim();
    }

    await onSubmit({
      rule_name: ruleName.trim() || null,
      destination_label: destinationLabel.trim() || null,
      destination_type: destinationType,
      custom_ai_instructions: customAiInstructions.trim() || null,
      destination_webhook_url: url,
      payload_version: version,
      symbol_mappings: mappings,
      risk_overrides: riskOverrides,
      webhook_body_template: parsedTemplate,
      enabled_actions: Array.from(enabledActions),
      keyword_blacklist: keywords,
      is_active: isActive,
    });
  }

  return (
    <div className="space-y-4">
      {/* Route Name */}
      <div className="space-y-1.5">
        <Label htmlFor="edit-rule-name" className="text-xs">Route Name (optional)</Label>
        <Input
          id="edit-rule-name"
          value={ruleName}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRuleName(e.target.value)}
          placeholder="e.g., Gold Aggressive, EURUSD Demo"
          className="h-8 text-sm"
        />
      </div>

      {/* Active Toggle */}
      <div className="flex items-center justify-between rounded-md border px-3 py-2">
        <div>
          <Label htmlFor="edit-is-active" className="text-xs">Status</Label>
          <p className="text-[10px] text-muted-foreground">
            {isActive ? "Actively routing signals" : "Paused"}
          </p>
        </div>
        <Switch
          id="edit-is-active"
          checked={isActive}
          onCheckedChange={setIsActive}
        />
      </div>

      {/* Account Label */}
      <div className="space-y-1.5">
        <Label htmlFor="edit-destination-label" className="text-xs">Account Label (optional)</Label>
        <Input
          id="edit-destination-label"
          value={destinationLabel}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setDestinationLabel(e.target.value)}
          placeholder="e.g., FTMO Challenge, Live Account"
          className="h-8 text-sm"
        />
      </div>

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
      <div className="space-y-1.5">
        <Label htmlFor="edit-webhook-url" className="text-xs">Webhook URL</Label>
        <div className="flex gap-2">
          <Input
            id="edit-webhook-url"
            type="url"
            value={url}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
              setUrl(e.target.value);
              if (urlError) setUrlError("");
              if (testStatus !== "idle") setTestStatus("idle");
            }}
            className="flex-1 h-8 text-sm font-mono"
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
        {urlError && <p className="text-[11px] text-destructive">{urlError}</p>}
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
              {matchingRules.map((r) => (
                <div key={r.id} className="flex items-center justify-between gap-2 mt-1.5">
                  <p className="text-[11px] text-muted-foreground truncate">
                    {r.rule_name || r.destination_label || "Unnamed route"}
                    <span className="ml-1 opacity-60">
                      ({DESTINATION_TYPES.find((dt) => dt.value === r.destination_type)?.label ?? r.destination_type}, {r.payload_version || "V1"})
                    </span>
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-6 text-[10px] shrink-0"
                    onClick={() => applyFromRule(r)}
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
      <div className="space-y-1.5">
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
                <RadioGroupItem value="V1" id="edit-v1" />
                <Label htmlFor="edit-v1" className="cursor-pointer text-xs">
                  <span className="font-medium">V1</span>
                  <span className="block text-[10px] text-muted-foreground mt-0.5">Strategy trigger — sends entry, close, and breakeven commands. (No Price/TP/SL)</span>
                </Label>
              </div>
              <div className="flex items-center space-x-2 rounded-md border px-3 py-2 flex-1">
                <RadioGroupItem value="V2" id="edit-v2" />
                <Label htmlFor="edit-v2" className="cursor-pointer text-xs">
                  <span className="font-medium">V2</span>
                  <span className="block text-[10px] text-muted-foreground mt-0.5">Full signal — includes entry, TP, SL, and lot size</span>
                </Label>
              </div>
            </div>
          </RadioGroup>
        )}
      </div>

      {/* Webhook Body Template */}
      <TemplateBuilder
        value={templateText}
        onChange={(text) => {
          setTemplateText(text);
          if (templateError) setTemplateError("");
        }}
        error={templateError}
      />

      {/* Template mismatch warning */}
      {templateWarning && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2">
          <p className="text-[11px] text-amber-600 dark:text-amber-400">{templateWarning}</p>
        </div>
      )}

      {/* Lot Size (V2 only) */}
      {version === "V2" && (
        <div className="space-y-1.5">
          <Label htmlFor="edit-lot-size" className="text-xs">Lot Size Override</Label>
          <Input
            id="edit-lot-size"
            type="text"
            inputMode="decimal"
            placeholder="e.g., 0.1 (leave empty for signal default)"
            value={lotSize}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setLotSize(e.target.value)
            }
            className="h-8 text-sm"
          />
        </div>
      )}

      {/* Advanced Settings */}
      <div>
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", showAdvanced && "rotate-180")} />
          Advanced Settings
        </button>
        {showAdvanced && (
          <div className="mt-3 space-y-1.5">
            <Label htmlFor="edit-ai-instructions" className="text-xs">Custom AI Instructions (optional)</Label>
            <Textarea
              id="edit-ai-instructions"
              value={customAiInstructions}
              onChange={(e) => setCustomAiInstructions(e.target.value)}
              placeholder='e.g., "When the provider says Layer 2, treat it as a new entry. Map US30 to DJI."'
              className="min-h-[80px] text-sm resize-y"
            />
            <p className="text-[10px] text-muted-foreground">
              Tell the AI how to interpret signals from this channel. These instructions are appended to the parser's system prompt.
            </p>

            {/* Keyword Blacklist */}
            <div className="mt-4 space-y-1.5">
              <Label className="text-xs">Keyword Blacklist</Label>
              <p className="text-[10px] text-muted-foreground">
                Messages containing any of these keywords will be ignored for this route.
              </p>
              <div className="flex gap-2">
                <Input
                  type="text"
                  placeholder="e.g., demo, paper trade"
                  value={keywordInput}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setKeywordInput(e.target.value)}
                  onKeyDown={(e: React.KeyboardEvent) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      const kw = keywordInput.trim();
                      if (kw && !keywords.includes(kw)) {
                        setKeywords((prev) => [...prev, kw]);
                      }
                      setKeywordInput("");
                    }
                  }}
                  className="h-8 text-sm flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8"
                  onClick={() => {
                    const kw = keywordInput.trim();
                    if (kw && !keywords.includes(kw)) {
                      setKeywords((prev) => [...prev, kw]);
                    }
                    setKeywordInput("");
                  }}
                  disabled={!keywordInput.trim()}
                >
                  Add
                </Button>
              </div>
              {keywords.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {keywords.map((kw) => (
                    <span
                      key={kw}
                      className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-xs"
                    >
                      {kw}
                      <button
                        type="button"
                        onClick={() => setKeywords((prev) => prev.filter((k) => k !== kw))}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        &times;
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Symbol Mappings */}
      <div className="space-y-2">
        <Label className="text-xs">Symbol Mappings</Label>
        <p className="text-[10px] text-muted-foreground">
          Map signal provider symbols to your broker's symbols. Example: GOLD → XAUUSD
        </p>

        {pairs.length > 0 && (
          <div className="space-y-1.5">
            {pairs.map((pair, i) => (
              <div key={i} className="flex items-center gap-1.5 rounded-md bg-muted/30 px-2 py-1">
                <Input
                  placeholder="GOLD"
                  value={pair.from}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    updatePair(i, "from", e.target.value)
                  }
                  className="h-7 text-xs font-mono flex-1"
                />
                <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
                <Input
                  placeholder="XAUUSD"
                  value={pair.to}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    updatePair(i, "to", e.target.value)
                  }
                  className="h-7 text-xs font-mono flex-1"
                />
                <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={() => removePair(i)}>
                  <X className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
        )}

        <Button variant="outline" size="sm" className="h-7 text-xs" onClick={addPair}>
          <Plus className="mr-1 h-3 w-3" />
          Add Mapping
        </Button>
      </div>

      {/* Enabled Actions */}
      <div>
        <button
          type="button"
          onClick={() => setShowActions(!showActions)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", showActions && "rotate-180")} />
          Enabled Actions
        </button>
        {showActions && (
          <div className="mt-3 space-y-1.5">
            <p className="text-[10px] text-muted-foreground mb-2">
              Choose which signal types get forwarded to this destination.
            </p>
            {getActionsForDestination(destinationType).map((action) => {
              const isEnabled = enabledActions.has(action.key);
              return (
                <div
                  key={action.key}
                  className={cn(
                    "flex items-center justify-between rounded-md border px-3 py-2 transition-colors",
                    isEnabled ? "border-border" : "border-border/50 bg-muted/30 opacity-60",
                  )}
                >
                  <div>
                    <p className="text-xs font-medium">{action.label}</p>
                    <p className="text-[10px] text-muted-foreground">{action.description}</p>
                  </div>
                  {action.isEntry ? (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div>
                            <Switch checked disabled className="opacity-50" />
                          </div>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="text-xs">Entry actions are always enabled</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  ) : (
                    <Switch
                      checked={isEnabled}
                      onCheckedChange={() => {
                        setEnabledActions((prev) => {
                          const next = new Set(prev);
                          if (next.has(action.key)) {
                            next.delete(action.key);
                          } else {
                            next.add(action.key);
                          }
                          return next;
                        });
                      }}
                    />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Form Actions */}
      <div className="flex gap-2 pt-2">
        <Button variant="outline" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        <Button size="sm" onClick={handleSubmit} disabled={isSubmitting || !url}>
          {isSubmitting ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </div>
  );
}
