import { Link } from "react-router-dom";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/shared/status-badge";
import { TelegramConnectForm } from "@/components/forms/telegram-connect-form";
import { useTelegramStatus } from "@/hooks/use-telegram";
import { usePageTitle } from "@/hooks/use-page-title";

export function TelegramPage() {
  usePageTitle("Telegram");
  const { data: status, isLoading } = useTelegramStatus();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Telegram Connection</h1>

      <Card className="max-w-lg">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Telegram Account</CardTitle>
              <CardDescription>
                Connect your Telegram account to receive signals.
              </CardDescription>
            </div>
            {isLoading ? (
              <Skeleton className="h-6 w-24" />
            ) : (
              <StatusBadge
                status={status?.connected ? "connected" : "disconnected"}
              />
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : status?.connected ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Your Telegram account is connected and receiving signals.
              </p>
              <div className="rounded-md border border-primary/20 bg-primary/5 p-4">
                <p className="text-sm font-medium">
                  Next step: Create a routing rule to start forwarding signals.
                </p>
                <Button asChild size="sm" className="mt-3">
                  <Link to="/routing-rules/new">Create Routing Rule</Link>
                </Button>
              </div>
            </div>
          ) : (
            <TelegramConnectForm />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
