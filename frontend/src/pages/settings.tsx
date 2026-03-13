import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
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
import { useAuth } from "@/contexts/auth-context";
import { Button } from "@/components/ui/button";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { getTierDisplayName } from "@/lib/tier";
import { TIER_COMPARISON } from "@/lib/tier";
import { cn } from "@/lib/utils";
import { usePageTitle } from "@/hooks/use-page-title";

export function SettingsPage() {
  usePageTitle("Settings");
  const { user, logout } = useAuth();
  const [showLogout, setShowLogout] = useState(false);

  if (!user) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>

      {/* Account */}
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>Your account information.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Email</p>
              <p className="text-sm text-muted-foreground">{user.email}</p>
            </div>
          </div>
          <div>
            <p className="text-sm font-medium">Joined</p>
            <p className="text-sm text-muted-foreground">
              {new Date(user.created_at).toLocaleDateString()}
            </p>
          </div>
          <Separator />
          <Button variant="destructive" onClick={() => setShowLogout(true)}>
            Sign Out
          </Button>
        </CardContent>
      </Card>

      <AlertDialog open={showLogout} onOpenChange={setShowLogout}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Sign out?</AlertDialogTitle>
            <AlertDialogDescription>
              You will need to sign in again to access your dashboard.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel variant="outline" size="default">Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="default"
              size="default"
              onClick={logout}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Sign Out
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Subscription */}
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Subscription</CardTitle>
          <CardDescription>
            Current plan:{" "}
            <Badge variant="secondary">
              {getTierDisplayName(user.subscription_tier)}
            </Badge>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {TIER_COMPARISON.map((t) => (
              <div
                key={t.tier}
                className={cn(
                  "rounded-lg border p-4 text-center",
                  t.tier === user.subscription_tier &&
                    "border-primary bg-primary/5"
                )}
              >
                <p className="text-sm font-semibold">{t.name}</p>
                <p className="mt-1 text-2xl font-bold">{t.price}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {t.maxRules} routing rule{t.maxRules !== 1 ? "s" : ""}
                </p>
                {t.tier === user.subscription_tier && (
                  <Badge className="mt-2" variant="secondary">
                    Current
                  </Badge>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
