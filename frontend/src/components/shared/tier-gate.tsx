import type { ReactNode } from "react";
import { ShieldAlert } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { getTierLimit, getTierDisplayName } from "@/lib/tier";
import { useRoutingRules } from "@/hooks/use-routing-rules";

interface TierGateProps {
  children: ReactNode;
}

export function TierGate({ children }: TierGateProps) {
  const { user } = useAuth();
  const { data: rules } = useRoutingRules();

  const tier = user?.subscription_tier || "free";
  const limit = getTierLimit(tier);
  // Count only active rules to match backend tier enforcement
  const count = rules?.filter((r) => r.is_active).length ?? 0;

  if (count >= limit) {
    return (
      <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-4">
        <div className="flex items-start gap-3">
          <ShieldAlert className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
          <div className="flex-1 space-y-2">
            <p className="text-sm font-medium">
              Rule limit reached ({count}/{limit})
            </p>
            <p className="text-xs text-muted-foreground">
              Your {getTierDisplayName(tier)} plan allows {limit} routing
              rule{limit !== 1 ? "s" : ""}.
              Paid plans with higher limits are coming soon.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

/**
 * Inline tier warning shown in the wizard when at limit.
 */
export function TierLimitBanner() {
  const { user } = useAuth();
  const { data: rules } = useRoutingRules();

  const tier = user?.subscription_tier || "free";
  const limit = getTierLimit(tier);
  // Count only active rules to match backend tier enforcement
  const count = rules?.filter((r) => r.is_active).length ?? 0;

  if (count < limit) return null;

  return (
    <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3">
      <div className="flex items-center gap-2">
        <ShieldAlert className="h-3.5 w-3.5 text-amber-500 shrink-0" />
        <p className="text-xs text-amber-700 dark:text-amber-300">
          You've reached the {getTierDisplayName(tier)} limit of {limit} route{limit !== 1 ? "s" : ""}.
          Paid plans with higher limits are coming soon.
        </p>
      </div>
    </div>
  );
}
