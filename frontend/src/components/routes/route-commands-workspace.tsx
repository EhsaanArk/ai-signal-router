import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  FlaskConical,
  Loader2,
  Lock,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useCopyToClipboard } from "@/hooks/use-clipboard";
import { useParsePreview } from "@/hooks/use-parse-preview";
import {
  getActionExamples,
  getActionsForDestination,
  getNormalizedEnabledActions,
  getUnsupportedForDestination,
  type ActionDefinition,
  type ActionExample,
} from "@/lib/action-definitions";
import { cn } from "@/lib/utils";
import type { DestinationType } from "@/types/api";

interface RouteCommandsWorkspaceProps {
  destinationType: DestinationType;
  enabledActions: Set<string>;
  onToggleAction: (key: string) => void;
  mode: "create" | "edit";
}

function SummaryStat({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "success" | "warning";
}) {
  return (
    <div className="rounded-xl border bg-muted/20 px-4 py-3">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p
        className={cn(
          "mt-1 text-sm font-semibold",
          tone === "success" && "text-emerald-600 dark:text-emerald-400",
          tone === "warning" && "text-amber-600 dark:text-amber-400",
        )}
      >
        {value}
      </p>
    </div>
  );
}

function ExampleChip({
  example,
  onTry,
  onCopy,
}: {
  example: ActionExample;
  onTry: (text: string) => void;
  onCopy: (text: string) => void;
}) {
  return (
    <div className="inline-flex items-center gap-1 rounded-full border bg-muted/30 pl-2 pr-1 py-1">
      <button
        type="button"
        onClick={() => onTry(example.text)}
        className="text-[11px] font-mono text-left text-foreground/85 hover:text-foreground transition-colors"
      >
        {example.text}
      </button>
      <button
        type="button"
        onClick={() => onCopy(example.text)}
        className="rounded-full p-1 text-muted-foreground hover:text-foreground transition-colors"
        aria-label={`Copy example ${example.label}`}
      >
        <Copy className="h-3 w-3" />
      </button>
    </div>
  );
}

function CommandCard({
  action,
  destinationType,
  isEnabled,
  onToggle,
  onTryExample,
  onCopyExample,
}: {
  action: ActionDefinition;
  destinationType: DestinationType;
  isEnabled: boolean;
  onToggle: (key: string) => void;
  onTryExample: (text: string) => void;
  onCopyExample: (text: string) => void;
}) {
  const examples = getActionExamples(action, destinationType);
  const isRequired = action.required || action.isEntry;

  return (
    <div
      className={cn(
        "rounded-2xl border p-4 transition-colors",
        isEnabled ? "border-border bg-card" : "border-border/60 bg-muted/20",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className="text-sm font-semibold">{action.label}</h4>
            {isRequired ? (
              <Badge variant="outline" className="gap-1 text-[10px]">
                <Lock className="h-3 w-3" />
                Required
              </Badge>
            ) : (
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px]",
                  isEnabled
                    ? "border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
                    : "border-border text-muted-foreground",
                )}
              >
                {isEnabled ? "Enabled" : "Disabled"}
              </Badge>
            )}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{action.description}</p>
        </div>
        {isRequired ? (
          <div className="rounded-full border border-border bg-muted/30 px-3 py-1 text-[11px] font-medium text-muted-foreground">
            Always on
          </div>
        ) : (
          <Switch
            checked={isEnabled}
            onCheckedChange={() => onToggle(action.key)}
            aria-label={`${action.label}: ${isEnabled ? "enabled" : "disabled"}`}
          />
        )}
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {examples.map((example) => (
          <ExampleChip
            key={`${action.key}-${example.text}`}
            example={example}
            onTry={onTryExample}
            onCopy={onCopyExample}
          />
        ))}
      </div>
    </div>
  );
}

function PreviewOutcomeCard({
  result,
}: {
  result: ReturnType<typeof useParsePreview>["data"];
}) {
  if (!result) return null;

  const isRecognized = result.is_valid_signal;
  const forwards = result.route_would_forward;
  const toneClasses = !isRecognized
    ? "border-border bg-muted/20"
    : forwards
      ? "border-emerald-500/30 bg-emerald-500/5"
      : "border-amber-500/30 bg-amber-500/5";

  const badgeLabel = !isRecognized
    ? "Not recognized"
    : forwards
      ? "Will forward"
      : result.destination_supported === false
        ? "Unsupported here"
        : "Recognized but blocked";

  return (
    <div className={cn("rounded-2xl border p-4 space-y-3", toneClasses)}>
      <div className="flex items-center gap-2 flex-wrap">
        <Badge
          variant="outline"
          className={cn(
            !isRecognized && "text-muted-foreground",
            forwards && "border-emerald-500/30 text-emerald-600 dark:text-emerald-400",
            isRecognized && !forwards && "border-amber-500/30 text-amber-600 dark:text-amber-400",
          )}
        >
          {badgeLabel}
        </Badge>
        {result.display_action_label && (
          <span className="text-sm font-semibold">{result.display_action_label}</span>
        )}
      </div>

      <p className="text-sm text-muted-foreground">
        {forwards
          ? "This route would forward the signal with the current command settings."
          : result.blocked_reason || result.ignore_reason || "This message would not be forwarded."}
      </p>

      {isRecognized && (
        <div className="grid grid-cols-2 gap-3 text-sm">
          {result.symbol && (
            <div>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Symbol</p>
              <p className="mt-1 font-medium">{result.symbol}</p>
            </div>
          )}
          {result.direction && (
            <div>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Direction</p>
              <p className="mt-1 font-medium capitalize">{result.direction}</p>
            </div>
          )}
          {result.order_type && (
            <div>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Order type</p>
              <p className="mt-1 font-medium capitalize">{result.order_type}</p>
            </div>
          )}
          {result.percentage != null && (
            <div>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Percentage</p>
              <p className="mt-1 font-medium">{result.percentage}%</p>
            </div>
          )}
          {result.entry_price != null && (
            <div>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Entry</p>
              <p className="mt-1 font-medium">{result.entry_price}</p>
            </div>
          )}
          {result.stop_loss != null && (
            <div>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Stop loss</p>
              <p className="mt-1 font-medium">{result.stop_loss}</p>
            </div>
          )}
          {result.take_profits.length > 0 && (
            <div className="col-span-2">
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Take profits</p>
              <p className="mt-1 font-medium">{result.take_profits.join(", ")}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function RouteCommandsWorkspace({
  destinationType,
  enabledActions,
  onToggleAction,
  mode,
}: RouteCommandsWorkspaceProps) {
  const actions = getActionsForDestination(destinationType);
  const unsupported = getUnsupportedForDestination(destinationType);
  const normalizedEnabledActions = getNormalizedEnabledActions(
    Array.from(enabledActions),
    destinationType,
  );
  const normalizedEnabledSet = new Set(normalizedEnabledActions);
  const entries = actions.filter((action) => action.category === "entries");
  const management = actions.filter((action) => action.category === "management");
  const enabledManagementCount = management.filter((action) => normalizedEnabledSet.has(action.key)).length;
  const disabledManagementCount = management.length - enabledManagementCount;
  const copy = useCopyToClipboard();
  const parsePreview = useParsePreview();
  const [testMessage, setTestMessage] = useState("");

  const placeholder = destinationType === "sagemaster_crypto"
    ? "Try a real crypto signal like: Buy BTC/USDT\nSL 64000\nTP 69000"
    : "Try a real forex signal like: Buy XAUUSD\nSL 2300\nTP 2350";

  function runPreview(message: string) {
    const trimmed = message.trim();
    if (!trimmed) return;
    setTestMessage(trimmed);
    parsePreview.mutate({
      message: trimmed,
      destination_type: destinationType,
      enabled_actions: normalizedEnabledActions,
    });
  }

  const helperText = mode === "create"
    ? "These settings will apply when you create the route."
    : "Save changes after reviewing commands and tester output.";

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <FlaskConical className="h-4 w-4 text-primary" />
          <h3 className="text-base font-semibold">Commands & Testing</h3>
        </div>
        <p className="text-sm text-muted-foreground">
          Review what this route understands, what is currently enabled, and test a real signal before saving.
        </p>
        <p className="text-[11px] text-muted-foreground">{helperText}</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryStat label="Required" value={`${entries.length} always on`} />
        <SummaryStat label="Enabled" value={`${enabledManagementCount} management commands`} tone="success" />
        <SummaryStat label="Disabled" value={`${disabledManagementCount} management commands`} tone={disabledManagementCount > 0 ? "warning" : "default"} />
        <SummaryStat label="Unsupported" value={`${unsupported.length} platform limits`} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.85fr)]">
        <div className="space-y-6">
          <section className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h4 className="text-sm font-semibold">Opens Trades</h4>
                <p className="text-sm text-muted-foreground">Required entry commands this route will always accept.</p>
              </div>
              <Badge variant="outline" className="text-[11px]">
                {entries.length} required
              </Badge>
            </div>
            <div className="grid gap-3">
              {entries.map((action) => (
                <CommandCard
                  key={action.key}
                  action={action}
                  destinationType={destinationType}
                  isEnabled
                  onToggle={onToggleAction}
                  onTryExample={runPreview}
                  onCopyExample={(text) => copy(text, "Example copied")}
                />
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h4 className="text-sm font-semibold">Manages Trades</h4>
                <p className="text-sm text-muted-foreground">Turn follow-up commands on or off for this route.</p>
              </div>
              <Badge variant="outline" className="text-[11px]">
                {enabledManagementCount}/{management.length} enabled
              </Badge>
            </div>
            <div className="grid gap-3">
              {management.map((action) => (
                <CommandCard
                  key={action.key}
                  action={action}
                  destinationType={destinationType}
                  isEnabled={normalizedEnabledSet.has(action.key)}
                  onToggle={onToggleAction}
                  onTryExample={runPreview}
                  onCopyExample={(text) => copy(text, "Example copied")}
                />
              ))}
            </div>
          </section>

          {unsupported.length > 0 && (
            <section className="space-y-3">
              <div>
                <h4 className="text-sm font-semibold">Won’t Work Here</h4>
                <p className="text-sm text-muted-foreground">Known platform limits for this destination.</p>
              </div>
              <div className="grid gap-3">
                {unsupported.map((item) => (
                  <div key={item.label} className="rounded-2xl border border-border/70 bg-muted/20 p-4">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-amber-500" />
                      <h5 className="text-sm font-semibold">{item.label}</h5>
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">{item.reason}</p>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        <aside className="space-y-3 xl:sticky xl:top-6 self-start">
          <div className="rounded-2xl border bg-card p-4 space-y-3">
            <div className="flex items-center gap-2">
              <FlaskConical className="h-4 w-4 text-primary" />
              <h4 className="text-sm font-semibold">Test This Route</h4>
            </div>
            <p className="text-sm text-muted-foreground">
              Paste a real Telegram signal to see whether this route would forward it with the current settings.
            </p>
            <Textarea
              value={testMessage}
              onChange={(event) => setTestMessage(event.target.value)}
              placeholder={placeholder}
              className="min-h-[160px] font-mono text-sm"
              maxLength={2000}
              disabled={parsePreview.isPending}
            />
            <Button
              type="button"
              className="w-full"
              onClick={() => runPreview(testMessage)}
              disabled={!testMessage.trim() || parsePreview.isPending}
            >
              {parsePreview.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Preview outcome
            </Button>
          </div>

          {parsePreview.isPending && (
            <div className="flex items-center gap-2 rounded-2xl border bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Checking how the parser and route settings would handle this message...
            </div>
          )}

          {parsePreview.data && (
            <PreviewOutcomeCard result={parsePreview.data} />
          )}

          {parsePreview.data?.route_would_forward && (
            <div className="flex items-center gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">
              <CheckCircle2 className="h-4 w-4" />
              This message matches the current route settings.
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
