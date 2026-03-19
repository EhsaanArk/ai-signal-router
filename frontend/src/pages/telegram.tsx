import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/shared/status-badge";
import { TelegramConnectForm } from "@/components/forms/telegram-connect-form";
import { AlertTriangle } from "lucide-react";
import { useTelegramStatus, useDisconnectTelegram } from "@/hooks/use-telegram";
import { useChannels } from "@/hooks/use-channels";
import { useRoutingRules } from "@/hooks/use-routing-rules";
import { usePageTitle } from "@/hooks/use-page-title";
import { formatRelativeTime } from "@/lib/utils";
import { toast } from "sonner";

const DISCONNECT_MESSAGES: Record<string, string> = {
  session_expired:
    "Your Telegram session expired. This can happen when you log out from another device or Telegram revokes the session.",
  flood_wait_exhausted:
    "Telegram temporarily rate-limited your account. Please wait a few minutes before reconnecting.",
  user_disconnected: "You disconnected your Telegram account.",
  decrypt_failed:
    "There was an issue with your session data. Please reconnect.",
};

export function TelegramPage() {
  usePageTitle("Telegram");
  const navigate = useNavigate();
  const { data: status, isLoading } = useTelegramStatus();
  const disconnect = useDisconnectTelegram();
  const [showDisconnect, setShowDisconnect] = useState(false);
  const [showAllChannels, setShowAllChannels] = useState(false);
  const { data: channels, isLoading: channelsLoading } = useChannels();
  const { data: rules } = useRoutingRules();

  const channelsWithActiveRoutes = new Set(
    (rules ?? []).filter((r) => r.is_active).map((r) => r.source_channel_id),
  );

  const activeCount = channels?.filter((ch) => channelsWithActiveRoutes.has(ch.id)).length ?? 0;

  // Auto-flip to "All Channels" when there are zero active channels
  useEffect(() => {
    if (!channelsLoading && activeCount === 0 && channels && channels.length > 0) {
      setShowAllChannels(true);
    }
  }, [channelsLoading, activeCount, channels]);

  function handleConnectSuccess() {
    toast.success("Telegram connected! Now create a route to start receiving signals.");
    // Redirect to setup wizard if setup not yet complete
    if (!localStorage.getItem("sgm_setup_complete")) {
      navigate("/setup");
    }
  }

  async function handleDisconnect() {
    try {
      await disconnect.mutateAsync();
      toast.success("Telegram disconnected");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to disconnect"
      );
    } finally {
      setShowDisconnect(false);
    }
  }

  return (
    <div className="max-w-lg">
      <Card>
        <CardHeader className="pb-3 pt-4 px-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium">Telegram Account</CardTitle>
            {isLoading ? (
              <Skeleton className="h-5 w-20" />
            ) : (
              <StatusBadge
                status={status?.connected ? "connected" : "disconnected"}
              />
            )}
          </div>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          {isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : status?.connected ? (
            /* ---- Connected state ---- */
            <div className="space-y-4">
              {/* Account info */}
              <div className="space-y-1.5">
                {status.phone_number && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Phone</span>
                    <span className="font-medium">{status.phone_number}</span>
                  </div>
                )}
                {status.connected_at && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Connected</span>
                    <span className="font-medium">
                      {formatRelativeTime(status.connected_at)}
                      <span className="text-muted-foreground ml-1">
                        ({new Date(status.connected_at).toLocaleDateString()})
                      </span>
                    </span>
                  </div>
                )}
              </div>

              <div className="h-px bg-border" />

              {/* Subscribed Channels */}
              <div>
                {(() => {
                  const displayChannels = showAllChannels
                    ? (channels ?? [])
                    : (channels?.filter((ch) => channelsWithActiveRoutes.has(ch.id)) ?? []);
                  const totalCount = channels?.length ?? 0;

                  return (
                    <>
                      <h3 className="text-xs font-medium mb-2">
                        {showAllChannels ? "All Channels" : "Active Channels"}
                        <span className="ml-1.5 text-muted-foreground">
                          ({showAllChannels ? totalCount : activeCount})
                        </span>
                      </h3>
                      {channelsLoading ? (
                        <div className="space-y-1.5">
                          {Array.from({ length: 3 }).map((_, i) => (
                            <Skeleton key={i} className="h-10 w-full" />
                          ))}
                        </div>
                      ) : displayChannels.length > 0 ? (
                        <div className="space-y-1.5">
                          {displayChannels.map((ch) => (
                            <div
                              key={ch.id}
                              className="flex items-center justify-between rounded-md border px-3 py-2"
                            >
                              <div className="min-w-0">
                                <p className="text-xs font-medium truncate">{ch.title}</p>
                                {ch.username && (
                                  <p className="text-[11px] text-muted-foreground">
                                    @{ch.username}
                                  </p>
                                )}
                              </div>
                              {channelsWithActiveRoutes.has(ch.id) ? (
                                <StatusBadge status="active" />
                              ) : (
                                <Button asChild variant="ghost" size="sm" className="h-6 text-[11px]">
                                  <Link to={`/routing-rules/new?channel=${ch.id}`}>
                                    + Route
                                  </Link>
                                </Button>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="space-y-2">
                          <p className="text-xs text-muted-foreground">
                            {showAllChannels
                              ? "No channels found. Join a Telegram channel to get started."
                              : "No active channels yet. Create a route to start receiving signals from a channel."}
                          </p>
                          {!showAllChannels && (
                            <Button asChild variant="outline" size="sm" className="h-7 text-[11px]">
                              <Link to="/routing-rules/new">Create your first route</Link>
                            </Button>
                          )}
                        </div>
                      )}
                      {totalCount > activeCount && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 text-[11px] mt-2 w-full"
                          onClick={() => setShowAllChannels((v) => !v)}
                        >
                          {showAllChannels
                            ? `Show active only (${activeCount})`
                            : `Show all channels (${totalCount})`}
                        </Button>
                      )}
                    </>
                  );
                })()}
              </div>

              <div className="h-px bg-border" />

              {/* Disconnect */}
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs text-destructive hover:text-destructive"
                onClick={() => setShowDisconnect(true)}
              >
                Disconnect
              </Button>
            </div>
          ) : (
            /* ---- Disconnected state ---- */
            <div className="space-y-4">
              {status?.disconnected_reason && status.disconnected_reason !== "user_disconnected" && (
                <div className="flex gap-2 bg-amber-500/10 border border-amber-500/20 rounded-md px-3 py-2.5">
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="text-xs text-amber-600 dark:text-amber-400">
                      {DISCONNECT_MESSAGES[status.disconnected_reason] ||
                        "Your Telegram session was disconnected."}
                    </p>
                    {status.disconnected_at && (
                      <p className="text-[10px] text-muted-foreground">
                        Disconnected {formatRelativeTime(status.disconnected_at)}
                      </p>
                    )}
                  </div>
                </div>
              )}
              <TelegramConnectForm
                onSuccess={handleConnectSuccess}
                defaultPhone={status?.phone_number ?? undefined}
              />
            </div>
          )}
        </CardContent>
      </Card>

      <AlertDialog open={showDisconnect} onOpenChange={setShowDisconnect}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Disconnect Telegram?</AlertDialogTitle>
            <AlertDialogDescription>
              This will stop all signal forwarding. Your routes will
              remain but won't receive new signals until you reconnect.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel variant="outline" size="default">Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="default"
              size="default"
              onClick={handleDisconnect}
              disabled={disconnect.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {disconnect.isPending ? "Disconnecting..." : "Disconnect"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default TelegramPage;
