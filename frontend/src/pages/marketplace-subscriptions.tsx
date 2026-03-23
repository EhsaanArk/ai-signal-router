import { useNavigate } from "react-router-dom";
import { Store } from "lucide-react";
import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
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
import { usePageTitle } from "@/hooks/use-page-title";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Subscription {
  id: string;
  provider_name: string;
  asset_class: string;
  status: "active" | "paused";
  subscribed_at: string;
}

// ---------------------------------------------------------------------------
// Hooks (co-located — user-facing, not admin)
// ---------------------------------------------------------------------------

function useMySubscriptions() {
  return useQuery({
    queryKey: ["marketplace-subscriptions"],
    queryFn: () => apiFetch<Subscription[]>("/marketplace/subscriptions"),
  });
}

function useUnsubscribe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (subscriptionId: string) =>
      apiFetch<void>(`/marketplace/subscriptions/${subscriptionId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["marketplace-subscriptions"] });
    },
  });
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function MarketplaceSubscriptionsPage() {
  usePageTitle("My Subscriptions");
  const navigate = useNavigate();
  const { data: subscriptions, isLoading } = useMySubscriptions();
  const unsubscribe = useUnsubscribe();
  const [unsubId, setUnsubId] = useState<string | null>(null);

  async function handleUnsubscribe() {
    if (!unsubId) return;
    try {
      await unsubscribe.mutateAsync(unsubId);
      toast.success("Unsubscribed successfully");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to unsubscribe"
      );
    } finally {
      setUnsubId(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-medium">My Subscriptions</h1>
        <Button
          size="sm"
          className="h-7 text-xs"
          onClick={() => navigate("/marketplace")}
        >
          <Store className="mr-1 h-3 w-3" />
          Browse Marketplace
        </Button>
      </div>

      {isLoading ? (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">Provider</TableHead>
                <TableHead className="text-xs">Asset Class</TableHead>
                <TableHead className="text-xs">Status</TableHead>
                <TableHead className="text-xs">Subscribed</TableHead>
                <TableHead className="text-xs w-24" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from({ length: 3 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 5 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-20" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : !subscriptions?.length ? (
        <EmptyState
          icon={Store}
          title="No subscriptions yet"
          description="Browse the marketplace to find signal providers and subscribe to start receiving signals."
          actionLabel="Browse Marketplace"
          onAction={() => navigate("/marketplace")}
        />
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">Provider</TableHead>
                <TableHead className="text-xs">Asset Class</TableHead>
                <TableHead className="text-xs">Status</TableHead>
                <TableHead className="text-xs">Subscribed</TableHead>
                <TableHead className="text-xs w-24" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {subscriptions.map((sub) => (
                <TableRow key={sub.id}>
                  <TableCell className="text-xs font-medium">
                    {sub.provider_name}
                  </TableCell>
                  <TableCell className="text-xs capitalize">
                    {sub.asset_class}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={sub.status === "active" ? "default" : "secondary"}
                      className="text-[10px]"
                    >
                      {sub.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(sub.subscribed_at).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs text-destructive hover:text-destructive"
                      onClick={() => setUnsubId(sub.id)}
                    >
                      Unsubscribe
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Unsubscribe Confirmation */}
      <AlertDialog
        open={!!unsubId}
        onOpenChange={(open: boolean) => !open && setUnsubId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unsubscribe from provider?</AlertDialogTitle>
            <AlertDialogDescription>
              You will stop receiving signals from this provider. You can
              re-subscribe at any time from the marketplace.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleUnsubscribe}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Unsubscribe
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default MarketplaceSubscriptionsPage;
