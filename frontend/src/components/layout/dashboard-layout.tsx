import { Suspense, useState } from "react";
import { Link, Outlet } from "react-router-dom";
import { ArrowRight, X } from "lucide-react";
import { Sidebar } from "./sidebar";
import { Header } from "./header";
import { MobileNav } from "./mobile-nav";
import { EmailVerifyBanner } from "@/components/shared/email-verify-banner";
import { PageLoader } from "@/components/shared/loading-spinner";
import { NavigationProgress } from "@/components/shared/navigation-progress";
import { OfflineBanner } from "@/components/shared/offline-banner";
import { VersionToast } from "@/components/shared/version-toast";
import { useRoutingRules } from "@/hooks/use-routing-rules";
import { useTelegramDisconnectAlert } from "@/hooks/use-telegram-disconnect-alert";

function SuspenseFallback() {
  return (
    <>
      <NavigationProgress />
      <PageLoader />
    </>
  );
}

function SetupIncompleteBanner() {
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem("sgm_setup_dismissed") === "true",
  );
  const { data: rules, isLoading } = useRoutingRules();

  const setupComplete = localStorage.getItem("sgm_setup_complete") === "true";
  const hasRules = (rules?.length ?? 0) > 0;

  if (dismissed || isLoading || (setupComplete && hasRules)) return null;

  return (
    <div className="mb-3 flex items-center justify-between gap-3 rounded-md border border-primary/30 bg-primary/5 px-3 py-2">
      <p className="text-xs text-muted-foreground">
        You haven't finished setting up.{" "}
        <Link to="/setup" className="font-medium text-primary hover:underline inline-flex items-center gap-1">
          Complete setup <ArrowRight className="h-3 w-3" />
        </Link>
      </p>
      <button
        onClick={() => {
          setDismissed(true);
          localStorage.setItem("sgm_setup_dismissed", "true");
        }}
        className="text-muted-foreground hover:text-foreground shrink-0"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function DashboardLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  useTelegramDisconnectAlert();

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar className="hidden lg:flex" />
      <MobileNav open={mobileOpen} onOpenChange={setMobileOpen} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header onMenuClick={() => setMobileOpen(true)} />
        <main className="flex-1 overflow-y-auto p-3 md:p-4 lg:p-5">
          <OfflineBanner />
          <EmailVerifyBanner />
          <SetupIncompleteBanner />
          <Suspense fallback={<SuspenseFallback />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
      <VersionToast />
    </div>
  );
}
