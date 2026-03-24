import { useNavigate } from "react-router-dom";
import { AlertTriangle, Store } from "lucide-react";
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
import { useMySubscriptions, useUnsubscribe } from "@/hooks/use-marketplace";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function MarketplaceSubscriptionsPage() {
  usePageTitle("My Subscriptions");
  const navigate = useNavigate();
  const { data: subscriptions, isLoading, isError, refetch } = useMySubscriptions();
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

      {isError ? (
        <div className="flex items-center gap-2 rounded-md border border-rose-500/20 bg-rose-500/5 px-3 py-2">
          <AlertTriangle className="h-3.5 w-3.5 text-rose-400 shrink-0" />
          <p className="flex-1 text-xs text-rose-400">Failed to load subscriptions.</p>
          <Button variant="ghost" size="sm" className="h-6 text-[11px] text-rose-400" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      ) : isLoading ? (
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
                <TableRow key={sub.subscription_id}>
                  <TableCell className="text-xs font-medium">
                    {sub.provider_name}
                  </TableCell>
                  <TableCell className="text-xs capitalize">
                    {sub.provider_asset_class}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={sub.is_active ? "default" : "secondary"}
                      className="text-[10px]"
                    >
                      {sub.is_active ? "active" : "paused"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(sub.created_at).toLocaleDateString("en-US", {
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
                      onClick={() => setUnsubId(sub.provider_id)}
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
