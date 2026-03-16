import { useState } from "react";
import { Bell, LogOut, Mail, Calendar, Shield, MessageCircle, ExternalLink } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { PageLoader } from "@/components/shared/loading-spinner";
import { apiFetch } from "@/lib/api";
import { getTierDisplayName, TIER_COMPARISON } from "@/lib/tier";
import { cn } from "@/lib/utils";
import { usePageTitle } from "@/hooks/use-page-title";
import { Switch } from "@/components/ui/switch";
import { useNotificationPreferences, useUpdateNotificationPreferences, useTelegramBotLink } from "@/hooks/use-notifications";
import { toast } from "sonner";
import type { MessageResponse } from "@/types/api";

const tierColors: Record<string, string> = {
  free: "border-zinc-500/30",
  starter: "border-blue-500/30 bg-blue-500/5",
  pro: "border-violet-500/30 bg-violet-500/5",
  elite: "border-amber-500/30 bg-amber-500/5",
};

const tierBadgeColors: Record<string, string> = {
  free: "text-zinc-500",
  starter: "text-blue-500",
  pro: "text-violet-500",
  elite: "text-amber-500",
};

export function SettingsPage() {
  usePageTitle("Settings");
  const { user, logout } = useAuth();
  const [showLogout, setShowLogout] = useState(false);

  if (!user) return <PageLoader />;

  const tier = user.subscription_tier;

  return (
    <div className="space-y-4 max-w-2xl">
      {/* Account */}
      <Card>
        <CardHeader className="pb-3 pt-4 px-4">
          <CardTitle className="text-sm font-medium">Account</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 space-y-3">
          <div className="flex items-center gap-3">
            <Mail className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <div>
              <p className="text-xs text-muted-foreground">Email</p>
              <p className="text-sm">{user.email}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Calendar className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <div>
              <p className="text-xs text-muted-foreground">Member since</p>
              <p className="text-sm">
                {new Date(user.created_at).toLocaleDateString("en-US", {
                  month: "long",
                  year: "numeric",
                })}
              </p>
            </div>
          </div>
          <Separator />
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs text-destructive hover:text-destructive"
            onClick={() => setShowLogout(true)}
          >
            <LogOut className="mr-1.5 h-3 w-3" />
            Sign Out
          </Button>
        </CardContent>
      </Card>

      {/* Security */}
      <ChangePasswordCard />

      {/* Notifications */}
      <NotificationsCard />

      {/* Subscription */}
      <Card>
        <CardHeader className="pb-3 pt-4 px-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium">Subscription</CardTitle>
            <span className={cn("text-xs font-bold uppercase tracking-wider", tierBadgeColors[tier] || "text-zinc-500")}>
              {getTierDisplayName(tier)}
            </span>
          </div>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {TIER_COMPARISON.map((t) => {
              const isCurrent = t.tier === tier;
              return (
                <div
                  key={t.tier}
                  className={cn(
                    "rounded-md border p-3 text-center transition-colors",
                    isCurrent
                      ? tierColors[t.tier] || "border-primary bg-primary/5"
                      : "hover:bg-muted/50"
                  )}
                >
                  <p className="text-xs font-semibold">{t.name}</p>
                  <p className="mt-1 text-lg font-bold font-tabular">{t.price}</p>
                  <p className="text-[10px] text-muted-foreground">
                    {t.maxRules} route{t.maxRules !== 1 ? "s" : ""}
                  </p>
                  {isCurrent ? (
                    <span className="mt-2 inline-block text-[10px] font-medium text-muted-foreground">
                      Current
                    </span>
                  ) : (
                    <span className="mt-2 inline-block text-[10px] font-medium text-muted-foreground/50">
                      Coming Soon
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Logout dialog */}
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
    </div>
  );
}

function ChangePasswordCard() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setIsSubmitting(true);
    try {
      await apiFetch<MessageResponse>("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      toast.success("Password changed");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to change password"
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3 pt-4 px-4">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Shield className="h-3.5 w-3.5 text-muted-foreground" />
          Security
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4">
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="current-password" className="text-xs">Current Password</Label>
            <Input
              id="current-password"
              type="password"
              className="h-8 text-sm"
              value={currentPassword}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setCurrentPassword(e.target.value)
              }
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-password" className="text-xs">New Password</Label>
            <Input
              id="new-password"
              type="password"
              className="h-8 text-sm"
              value={newPassword}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                setNewPassword(e.target.value);
                if (error) setError("");
              }}
              required
              minLength={8}
            />
            <p className="text-[10px] text-muted-foreground">Min. 8 characters</p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="confirm-password" className="text-xs">Confirm Password</Label>
            <Input
              id="confirm-password"
              type="password"
              className="h-8 text-sm"
              value={confirmPassword}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                setConfirmPassword(e.target.value);
                if (error) setError("");
              }}
              required
            />
          </div>
          {error && <p className="text-[11px] text-destructive">{error}</p>}
          <Button type="submit" size="sm" className="h-7 text-xs" disabled={isSubmitting}>
            {isSubmitting ? "Changing..." : "Change Password"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function NotificationsCard() {
  const { user } = useAuth();
  const { data: prefs, isLoading } = useNotificationPreferences();
  const updatePrefs = useUpdateNotificationPreferences();
  const { data: botLink, isLoading: botLinkLoading } = useTelegramBotLink();

  const isFreeTier = user?.subscription_tier === "free";
  const hasTelegramLinked = !!prefs?.telegram_bot_chat_id;

  type NotifKey = "email_on_success" | "email_on_failure" | "telegram_on_success" | "telegram_on_failure";

  async function handleToggle(key: NotifKey, value: boolean) {
    try {
      await updatePrefs.mutateAsync({ [key]: value });
    } catch {
      toast.error("Failed to update notification preferences");
    }
  }

  if (isLoading) return null;

  return (
    <Card>
      <CardHeader className="pb-3 pt-4 px-4">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Bell className="h-3.5 w-3.5 text-muted-foreground" />
          Notifications
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4 space-y-3">
        {/* Email notifications */}
        <div className="flex items-center gap-2 mb-1">
          <Mail className="h-3 w-3 text-muted-foreground" />
          <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Email</span>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <Label htmlFor="notif-failure" className="text-xs">Email me when a signal fails to route</Label>
            <p className="text-[10px] text-muted-foreground">Get alerted when something goes wrong</p>
          </div>
          <Switch
            id="notif-failure"
            checked={prefs?.email_on_failure ?? true}
            onCheckedChange={(v) => handleToggle("email_on_failure", v)}
            disabled={updatePrefs.isPending}
          />
        </div>
        <div className="flex items-center justify-between">
          <div>
            <Label htmlFor="notif-success" className="text-xs">Email me on every successful signal</Label>
            <p className="text-[10px] text-muted-foreground">Confirmation for each routed signal</p>
          </div>
          <Switch
            id="notif-success"
            checked={prefs?.email_on_success ?? false}
            onCheckedChange={(v) => handleToggle("email_on_success", v)}
            disabled={updatePrefs.isPending}
          />
        </div>

        <Separator />

        {/* Telegram notifications */}
        <div className="flex items-center gap-2 mb-1">
          <MessageCircle className="h-3 w-3 text-muted-foreground" />
          <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Telegram Bot</span>
          {isFreeTier && (
            <span className="text-[9px] bg-blue-500/10 text-blue-500 px-1.5 py-0.5 rounded">Starter+</span>
          )}
        </div>

        {isFreeTier ? (
          <p className="text-[10px] text-muted-foreground">
            Telegram notifications coming soon to paid plans.
          </p>
        ) : !hasTelegramLinked ? (
          <div className="space-y-2">
            <p className="text-[10px] text-muted-foreground">
              Connect the SageMaster notification bot to receive signal alerts in Telegram.
            </p>
            {botLink && !botLinkLoading && (
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                asChild
              >
                <a href={botLink.bot_link} target="_blank" rel="noopener noreferrer">
                  <MessageCircle className="mr-1.5 h-3 w-3" />
                  Connect Telegram Bot
                  <ExternalLink className="ml-1.5 h-2.5 w-2.5" />
                </a>
              </Button>
            )}
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="tg-notif-failure" className="text-xs">Telegram alert on failure</Label>
                <p className="text-[10px] text-muted-foreground">Get a Telegram message when routing fails</p>
              </div>
              <Switch
                id="tg-notif-failure"
                checked={prefs?.telegram_on_failure ?? false}
                onCheckedChange={(v) => handleToggle("telegram_on_failure", v)}
                disabled={updatePrefs.isPending}
              />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="tg-notif-success" className="text-xs">Telegram alert on success</Label>
                <p className="text-[10px] text-muted-foreground">Get a Telegram message for every routed signal</p>
              </div>
              <Switch
                id="tg-notif-success"
                checked={prefs?.telegram_on_success ?? false}
                onCheckedChange={(v) => handleToggle("telegram_on_success", v)}
                disabled={updatePrefs.isPending}
              />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
