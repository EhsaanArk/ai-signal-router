import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Copy, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Switch } from "@/components/ui/switch";
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
import { truncateText } from "@/lib/utils";
import { toast } from "sonner";
import type { RoutingRuleResponse } from "@/types/api";

interface Props {
  rules: RoutingRuleResponse[];
}

export function RoutingRulesTable({ rules }: Props) {
  const navigate = useNavigate();
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);
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
        `Rule ${rule.is_active ? "deactivated" : "activated"}`
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
      toast.success("Rule deleted");
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
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Source Channel</TableHead>
              <TableHead className="hidden md:table-cell">
                Destination
              </TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Active</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rules.map((rule) => (
              <TableRow key={rule.id}>
                <TableCell className="font-medium">
                  {rule.source_channel_name || rule.source_channel_id}
                  <span className="block md:hidden text-xs text-muted-foreground truncate">
                    {truncateText(rule.destination_webhook_url, 35)}
                  </span>
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="cursor-default">
                        {truncateText(rule.destination_webhook_url, 40)}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>
                      {rule.destination_webhook_url}
                    </TooltipContent>
                  </Tooltip>
                </TableCell>
                <TableCell>{rule.payload_version}</TableCell>
                <TableCell>
                  <Switch
                    checked={rule.is_active}
                    disabled={togglingId === rule.id}
                    onCheckedChange={() => handleToggle(rule)}
                  />
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => navigate(`/routing-rules/${rule.id}/edit`)}
                      >
                        <Pencil className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => {
                          navigator.clipboard.writeText(rule.destination_webhook_url).then(() =>
                            toast.success("Webhook URL copied")
                          );
                        }}
                      >
                        <Copy className="mr-2 h-4 w-4" />
                        Copy URL
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => setDeleteId(rule.id)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
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
            <AlertDialogTitle>Delete routing rule?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. The rule will stop forwarding
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
    </>
  );
}
