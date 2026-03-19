import { useState } from "react";
import { Brain, FlaskConical, Settings2, RotateCcw, Save, Pencil, X, Loader2, CheckCircle2, XCircle, Send } from "lucide-react";
import { toast } from "sonner";
import { usePageTitle } from "@/hooks/use-page-title";
import {
  useParserPrompt,
  useParserPromptHistory,
  useUpdateParserPrompt,
  useRevertParserPrompt,
  useParserModelConfig,
  useUpdateParserModel,
  useTestParse,
  useTestDispatch,
} from "@/hooks/use-admin-parser";
import { useRoutingRules } from "@/hooks/use-routing-rules";
import type { ValidationCheck } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";

type Tab = "prompt" | "sandbox" | "model";

const tabs: { key: Tab; label: string; icon: typeof Brain }[] = [
  { key: "prompt", label: "System Prompt", icon: Brain },
  { key: "sandbox", label: "Test Sandbox", icon: FlaskConical },
  { key: "model", label: "Model Config", icon: Settings2 },
];

// ---------------------------------------------------------------------------
// System Prompt Tab
// ---------------------------------------------------------------------------

function SystemPromptTab() {
  const { data: prompt, isLoading } = useParserPrompt();
  const { data: history, isLoading: historyLoading } = useParserPromptHistory();
  const updatePrompt = useUpdateParserPrompt();
  const revertPrompt = useRevertParserPrompt();

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [changeNote, setChangeNote] = useState("");
  const [revertTarget, setRevertTarget] = useState<string | null>(null);

  function startEditing() {
    setDraft(prompt?.system_prompt || "");
    setChangeNote("");
    setEditing(true);
  }

  function cancelEditing() {
    setEditing(false);
    setDraft("");
    setChangeNote("");
  }

  function handleSave() {
    updatePrompt.mutate(
      { system_prompt: draft, change_note: changeNote || undefined },
      {
        onSuccess: () => {
          toast.success("System prompt updated");
          setEditing(false);
        },
        onError: () => toast.error("Failed to update prompt"),
      }
    );
  }

  function handleRevert(versionId: string) {
    revertPrompt.mutate(versionId, {
      onSuccess: () => {
        toast.success("Prompt reverted");
        setRevertTarget(null);
      },
      onError: () => toast.error("Failed to revert"),
    });
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div>
            <CardTitle className="text-sm font-medium">Active System Prompt</CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              Version {prompt?.version ?? 0}
              {prompt?.changed_by_email && ` \u00b7 by ${prompt.changed_by_email}`}
            </p>
          </div>
          {!editing ? (
            <Button size="sm" variant="outline" onClick={startEditing}>
              <Pencil className="mr-1.5 h-3.5 w-3.5" />
              Edit
            </Button>
          ) : (
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={cancelEditing}
                disabled={updatePrompt.isPending}
              >
                <X className="mr-1.5 h-3.5 w-3.5" />
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleSave}
                disabled={updatePrompt.isPending || draft.length < 10}
              >
                {updatePrompt.isPending ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Save className="mr-1.5 h-3.5 w-3.5" />
                )}
                Save
              </Button>
            </div>
          )}
        </CardHeader>
        <CardContent className="space-y-3">
          {editing && (
            <Input
              placeholder="Change note (optional)"
              value={changeNote}
              onChange={(e) => setChangeNote(e.target.value)}
              className="text-xs"
            />
          )}
          <Textarea
            className="min-h-[400px] font-mono text-xs leading-relaxed"
            value={editing ? draft : prompt?.system_prompt || ""}
            onChange={(e) => setDraft(e.target.value)}
            readOnly={!editing}
          />
        </CardContent>
      </Card>

      {/* Version History */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">Version History</CardTitle>
        </CardHeader>
        <CardContent>
          {historyLoading ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !history?.items.length ? (
            <p className="text-xs text-muted-foreground py-4 text-center">
              No version history yet. Edit the prompt to create the first version.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">Version</TableHead>
                  <TableHead>Changed By</TableHead>
                  <TableHead>Note</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="w-20" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-mono text-xs">
                      v{item.version}
                      {item.is_active && (
                        <Badge variant="outline" className="ml-2 text-[10px]">
                          active
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-xs">
                      {item.changed_by_email || "\u2014"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate">
                      {item.change_note || "\u2014"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {item.created_at
                        ? new Date(item.created_at).toLocaleString()
                        : "\u2014"}
                    </TableCell>
                    <TableCell>
                      {!item.is_active && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 text-xs"
                          onClick={() => setRevertTarget(item.id)}
                        >
                          <RotateCcw className="mr-1 h-3 w-3" />
                          Revert
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Revert Confirmation Dialog */}
      <AlertDialog
        open={!!revertTarget}
        onOpenChange={(open) => !open && setRevertTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Revert system prompt?</AlertDialogTitle>
            <AlertDialogDescription>
              This will create a new version with the content from the selected
              version. The current prompt will be preserved in the history.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => revertTarget && handleRevert(revertTarget)}
            >
              Revert
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Test Sandbox Tab
// ---------------------------------------------------------------------------

function ValidationChecks({ checks }: { checks: ValidationCheck[] }) {
  if (!checks.length) return null;
  return (
    <div className="space-y-1.5">
      {checks.map((check, i) => (
        <div key={i} className="flex items-start gap-2 text-xs">
          {check.passed ? (
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 mt-0.5 shrink-0" />
          ) : (
            <XCircle className="h-3.5 w-3.5 text-rose-500 mt-0.5 shrink-0" />
          )}
          <span className={check.passed ? "text-muted-foreground" : "text-rose-600"}>
            <span className="font-medium">{check.name}:</span> {check.message}
          </span>
        </div>
      ))}
    </div>
  );
}

function TestSandboxTab() {
  const testParse = useTestParse();
  const testDispatch = useTestDispatch();
  const { data: rulesData } = useRoutingRules();
  const [rawMessage, setRawMessage] = useState("");
  const [customInstructions, setCustomInstructions] = useState("");
  const [selectedRuleId, setSelectedRuleId] = useState<string>("");

  const rules = rulesData ?? [];

  function handleParse() {
    testParse.mutate({
      raw_message: rawMessage,
      custom_instructions: customInstructions || undefined,
    });
  }

  function handleDispatch() {
    if (!selectedRuleId) return;
    testDispatch.mutate(
      {
        raw_message: rawMessage,
        routing_rule_id: selectedRuleId,
        custom_instructions: customInstructions || undefined,
      },
      {
        onSuccess: (data) => {
          if (data.status_code === 200) {
            toast.success("Webhook dispatched successfully");
          } else {
            toast.error(`Dispatch failed: ${data.response_body}`);
          }
        },
        onError: (err) =>
          toast.error(
            err instanceof Error ? err.message : "Dispatch failed"
          ),
      }
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">
            Test Signal Parser
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            Paste a raw signal message to test parsing, validation, and
            optionally dispatch to a webhook.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-xs font-medium mb-1.5 block">
              Raw Signal Message
            </label>
            <Textarea
              className="min-h-[120px] font-mono text-xs"
              placeholder="e.g. BUY XAUUSD @ 2650&#10;SL: 2640&#10;TP1: 2660&#10;TP2: 2670"
              value={rawMessage}
              onChange={(e) => setRawMessage(e.target.value)}
            />
          </div>

          <div>
            <label className="text-xs font-medium mb-1.5 block">
              Custom AI Instructions{" "}
              <span className="text-muted-foreground font-normal">
                (optional)
              </span>
            </label>
            <Textarea
              className="min-h-[60px] font-mono text-xs"
              placeholder="e.g. Treat all signals from this channel as crypto signals."
              value={customInstructions}
              onChange={(e) => setCustomInstructions(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-2">
            <Button
              onClick={handleParse}
              disabled={testParse.isPending || !rawMessage.trim()}
            >
              {testParse.isPending ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <FlaskConical className="mr-1.5 h-3.5 w-3.5" />
              )}
              Parse Signal
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Validation Checks */}
      {testParse.data?.validation_checks?.length ? (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">
              Validation Checks
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ValidationChecks checks={testParse.data.validation_checks} />
          </CardContent>
        </Card>
      ) : null}

      {/* Parse Result */}
      {testParse.data && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <CardTitle className="text-sm font-medium">
                Parse Result
              </CardTitle>
              <Badge variant="outline" className="text-[10px]">
                {testParse.data.model_used}
              </Badge>
              <Badge variant="outline" className="text-[10px]">
                temp: {testParse.data.temperature_used}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <pre className="rounded-md bg-muted p-4 text-xs font-mono overflow-auto max-h-[400px] leading-relaxed">
              {JSON.stringify(testParse.data.parsed, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}

      {/* Test Dispatch */}
      {testParse.data?.parsed?.is_valid_signal === true && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">
              Test Webhook Dispatch
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              Send this parsed signal to a routing rule's webhook for testing.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <label className="text-xs font-medium mb-1.5 block">
                Routing Rule
              </label>
              <Select value={selectedRuleId} onValueChange={setSelectedRuleId}>
                <SelectTrigger className="w-full max-w-md">
                  <SelectValue placeholder="Select a routing rule..." />
                </SelectTrigger>
                <SelectContent>
                  {(Array.isArray(rules) ? rules : []).map((rule: any) => (
                    <SelectItem key={rule.id} value={rule.id}>
                      {rule.rule_name || rule.source_channel_name || rule.source_channel_id}
                      {" \u2192 "}
                      {rule.destination_type}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={handleDispatch}
              disabled={testDispatch.isPending || !selectedRuleId}
              variant="outline"
            >
              {testDispatch.isPending ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <Send className="mr-1.5 h-3.5 w-3.5" />
              )}
              Send Test Webhook
            </Button>
            {testDispatch.data && (
              <p className={`text-xs ${testDispatch.data.status_code === 200 ? "text-emerald-600" : "text-rose-600"}`}>
                {testDispatch.data.response_body}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {testParse.isError && (
        <Card className="border-destructive/50">
          <CardContent className="pt-6">
            <p className="text-xs text-destructive">
              Parse failed:{" "}
              {testParse.error instanceof Error
                ? testParse.error.message
                : "Unknown error"}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Model Config Tab
// ---------------------------------------------------------------------------

function ModelConfigTab() {
  const { data: config, isLoading } = useParserModelConfig();
  const updateModel = useUpdateParserModel();

  const [modelName, setModelName] = useState<string | null>(null);
  const [temperature, setTemperature] = useState<number | null>(null);
  const [changeNote, setChangeNote] = useState("");

  const currentModel = modelName ?? config?.model_name ?? "gpt-4o-mini";
  const currentTemp = temperature ?? config?.temperature ?? 0;

  const hasChanges =
    currentModel !== (config?.model_name ?? "gpt-4o-mini") ||
    currentTemp !== (config?.temperature ?? 0);

  function handleSave() {
    updateModel.mutate(
      {
        model_name: currentModel,
        temperature: currentTemp,
        change_note: changeNote || undefined,
      },
      {
        onSuccess: () => {
          toast.success("Model configuration updated");
          setModelName(null);
          setTemperature(null);
          setChangeNote("");
        },
        onError: () => toast.error("Failed to update model config"),
      }
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">
            Model Configuration
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            Configure the OpenAI model and temperature used for signal parsing.
            Changes take effect within 5 minutes (or immediately for new
            signals after cache expiry).
          </p>
        </CardHeader>
        <CardContent className="space-y-5">
          <div>
            <label className="text-xs font-medium mb-1.5 block">Model</label>
            <Select value={currentModel} onValueChange={setModelName}>
              <SelectTrigger className="w-64">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="gpt-4o-mini">
                  gpt-4o-mini (fastest, cheapest)
                </SelectItem>
                <SelectItem value="gpt-4o">
                  gpt-4o (most capable)
                </SelectItem>
                <SelectItem value="gpt-4-turbo">
                  gpt-4-turbo (balanced)
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <label className="text-xs font-medium mb-1.5 block">
              Temperature:{" "}
              <span className="font-mono">{currentTemp.toFixed(2)}</span>
            </label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={currentTemp}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-64 accent-primary"
            />
            <div className="flex justify-between w-64 text-[10px] text-muted-foreground mt-1">
              <span>0.0 (deterministic)</span>
              <span>1.0 (creative)</span>
            </div>
          </div>

          {hasChanges && (
            <div className="space-y-3 pt-2 border-t">
              <Input
                placeholder="Change note (optional)"
                value={changeNote}
                onChange={(e) => setChangeNote(e.target.value)}
                className="text-xs w-64"
              />
              <Button
                onClick={handleSave}
                disabled={updateModel.isPending}
              >
                {updateModel.isPending ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Save className="mr-1.5 h-3.5 w-3.5" />
                )}
                Save Configuration
              </Button>
            </div>
          )}

          <div className="text-xs text-muted-foreground pt-2 border-t">
            Current active version: v{config?.version ?? 0}
            {config?.changed_by_email &&
              ` \u00b7 last changed by ${config.changed_by_email}`}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function AdminParserPage() {
  usePageTitle("Admin - AI Parser");
  const [activeTab, setActiveTab] = useState<Tab>("prompt");

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-medium">AI Parser Manager</h2>

      {/* Tab bar */}
      <div className="flex gap-1 rounded-lg bg-muted p-1 w-fit">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                isActive
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {activeTab === "prompt" && <SystemPromptTab />}
      {activeTab === "sandbox" && <TestSandboxTab />}
      {activeTab === "model" && <ModelConfigTab />}
    </div>
  );
}

export default AdminParserPage;
