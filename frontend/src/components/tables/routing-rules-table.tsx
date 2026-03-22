import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Copy, FileJson, ListChecks, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useDeleteRule, useUpdateRule } from "@/hooks/use-routing-rules";
import { DESTINATION_TYPE_LABELS_FULL } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { getActionBadge } from "@/lib/action-definitions";
import { CommandReferenceDrawer } from "@/components/command-reference-drawer";
import type { RoutingRuleResponse } from "@/types/api";

interface Props {
  rules: RoutingRuleResponse[];
}

export function RoutingRulesTable({ rules }: Props) {
  const navigate = useNavigate();
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [commandsRuleId, setCommandsRuleId] = useState<string | null>(null);
  const commandsRule = rules.find((r) => r.id === commandsRuleId);
  const isSageMaster = (dt: string) => dt === "sagemaster_forex" || dt === "sagemaster_crypto";
  const updateRule = useUpdateRule();
  const deleteRule = useDeleteRule();

  async function handleToggle(rule: RoutingRuleResponse) {
    setTogglingId(rule.id);
    try {
      await updateRule.mutateAsync({
        id: rule.id,
        data: { is_active: !rule.is_active },
      });
      toast.success(
        `Route ${rule.is_active ? "paused" : "activated"}`
      );
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to update rule"
      );
    } finally {
      setTogglingId(null);
    }
  }

  async function handleDelete() {
    if (!deleteId) return;
    try {
      await deleteRule.mutateAsync(deleteId);
      toast.success("Route deleted");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to delete rule"
      );
    } finally {
      setDeleteId(null);
    }
  }

  return (
    <>
      {/* Mobile card layout */}
      <div className="space-y-2 md:hidden">
        {rules.map((rule) => (
          <div
            key={rule.id}
            className={cn(
              "rounded-md border p-3 space-y-2 border-l-2",
              rule.is_active ? "border-l-emerald-500" : "border-l-zinc-400"
            )}
          >
            <div className="flex items-center justify-between">
              <div className="truncate flex-1">
                <span className="text-xs font-semibold truncate block">
                  {rule.rule_name || rule.source_channel_name || rule.source_channel_id}
                </span>
                {rule.rule_name && (
                  <span className="text-[10px] text-muted-foreground truncate block">
                    {rule.source_channel_name || rule.source_channel_id}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="rounded-sm border px-1.5 py-0.5 text-[10px] font-mono font-medium">
                  {rule.payload_version}
                </span>
                {isSageMaster(rule.destination_type) && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() => setCommandsRuleId(rule.id)}
                        className="rounded-sm border px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {getActionBadge(rule.enabled_actions, rule.destination_type)}
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>View signal commands</TooltipContent>
                  </Tooltip>
                )}
                {rule.webhook_body_template && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <FileJson className="h-3 w-3 text-muted-foreground" />
                    </TooltipTrigger>
                    <TooltipContent>Custom template</TooltipContent>
                  </Tooltip>
                )}
                <button
                  onClick={() => handleToggle(rule)}
                  disabled={togglingId === rule.id}
                  className="flex items-center gap-1.5"
                >
                  <span className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    rule.is_active ? "bg-emerald-500" : "bg-zinc-400"
                  )} />
                  <span className="text-[10px] text-muted-foreground">
                    {rule.is_active ? "Active" : "Paused"}
                  </span>
                </button>
              </div>
            </div>
            <div className="text-[10px] truncate">
              <p className="text-muted-foreground">
                {DESTINATION_TYPE_LABELS_FULL[rule.destination_type] || "SageMaster Forex"}
              </p>
              {rule.destination_label && (
                <p className="text-muted-foreground/70">{rule.destination_label}</p>
              )}
            </div>
            <div className="flex gap-1.5">
              <Button
                variant="outline"
                size="sm"
                className="flex-1 h-7 text-xs"
                onClick={() => navigate(`/routing-rules/${rule.id}/edit`)}
              >
                <Pencil className="mr-1 h-3 w-3" />
                Edit
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-7"
                onClick={() => {
                  navigator.clipboard.writeText(rule.destination_webhook_url).then(() =>
                    toast.success("URL copied")
                  );
                }}
              >
                <Copy className="h-3 w-3" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-destructive hover:text-destructive"
                onClick={() => setDeleteId(rule.id)}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          </div>
        ))}
      </div>

      {/* Desktop table layout */}
      <div className="hidden md:block rounded-md border">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="text-[11px]">Route</TableHead>
              <TableHead className="text-[11px]">Destination</TableHead>
              <TableHead className="w-16 text-[11px]">Format</TableHead>
              <TableHead className="w-8 text-[11px]" />
              <TableHead className="hidden lg:table-cell w-28 text-[11px]">Created</TableHead>
              <TableHead className="w-24 text-[11px]">Status</TableHead>
              <TableHead className="w-10 text-[11px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rules.map((rule) => (
              <TableRow key={rule.id} className="hover:bg-muted/40">
                <TableCell className="py-2">
                  <div>
                    <p className="text-xs font-semibold truncate max-w-[200px]">
                      {rule.rule_name || rule.source_channel_name || rule.source_channel_id}
                    </p>
                    {rule.rule_name && (
                      <p className="text-[10px] text-muted-foreground truncate max-w-[200px]">
                        {rule.source_channel_name || rule.source_channel_id}
                      </p>
                    )}
                  </div>
                </TableCell>
                <TableCell className="py-2">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="cursor-default">
                        <p className="text-[11px]">
                          {DESTINATION_TYPE_LABELS_FULL[rule.destination_type] || "SageMaster Forex"}
                        </p>
                        {rule.destination_label && (
                          <p className="text-[10px] text-muted-foreground">{rule.destination_label}</p>
                        )}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-sm break-all font-mono text-xs">
                      {rule.destination_webhook_url}
                    </TooltipContent>
                  </Tooltip>
                </TableCell>
                <TableCell className="py-2">
                  <div className="flex items-center gap-1.5">
                    <span className="rounded-sm border px-1.5 py-0.5 text-[10px] font-mono font-medium">
                      {rule.payload_version}
                    </span>
                    {isSageMaster(rule.destination_type) && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            onClick={() => setCommandsRuleId(rule.id)}
                            className="rounded-sm border px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground hover:text-foreground transition-colors"
                          >
                            {getActionBadge(rule.enabled_actions, rule.destination_type)}
                          </button>
                        </TooltipTrigger>
                        <TooltipContent>View signal commands</TooltipContent>
                      </Tooltip>
                    )}
                  </div>
                </TableCell>
                <TableCell className="py-2">
                  {rule.webhook_body_template && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <FileJson className="h-3.5 w-3.5 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent>Custom template configured</TooltipContent>
                    </Tooltip>
                  )}
                </TableCell>
                <TableCell className="hidden lg:table-cell py-2">
                  <span className="text-[10px] text-muted-foreground">
                    {rule.created_at
                      ? new Date(rule.created_at).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })
                      : "—"}
                  </span>
                </TableCell>
                <TableCell className="py-2">
                  <button
                    onClick={() => handleToggle(rule)}
                    disabled={togglingId === rule.id}
                    className="flex items-center gap-1.5 group"
                  >
                    <span className={cn(
                      "h-1.5 w-1.5 rounded-full transition-colors",
                      rule.is_active ? "bg-emerald-500" : "bg-zinc-400"
                    )} />
                    <span className="text-[11px] text-muted-foreground group-hover:text-foreground transition-colors">
                      {rule.is_active ? "Active" : "Paused"}
                    </span>
                  </button>
                </TableCell>
                <TableCell className="py-2">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-7 w-7">
                        <MoreHorizontal className="h-3.5 w-3.5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {isSageMaster(rule.destination_type) && (
                        <DropdownMenuItem
                          onClick={() => setCommandsRuleId(rule.id)}
                        >
                          <ListChecks className="mr-2 h-3.5 w-3.5" />
                          View Commands
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuItem
                        onClick={() => navigate(`/routing-rules/${rule.id}/edit`)}
                      >
                        <Pencil className="mr-2 h-3.5 w-3.5" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => {
                          navigator.clipboard.writeText(rule.destination_webhook_url).then(() =>
                            toast.success("URL copied")
                          );
                        }}
                      >
                        <Copy className="mr-2 h-3.5 w-3.5" />
                        Copy URL
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => setDeleteId(rule.id)}
                      >
                        <Trash2 className="mr-2 h-3.5 w-3.5" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <AlertDialog
        open={!!deleteId}
        onOpenChange={(open: boolean) => !open && setDeleteId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete route?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. The route will stop forwarding
              signals immediately.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel variant="outline" size="default">Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="default"
              size="default"
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {commandsRule && (
        <CommandReferenceDrawer
          rule={commandsRule}
          open={!!commandsRuleId}
          onOpenChange={(open) => !open && setCommandsRuleId(null)}
        />
      )}
    </>
  );
}
