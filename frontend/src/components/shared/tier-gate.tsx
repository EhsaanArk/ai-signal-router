import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ShieldAlert } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { getTierLimit, getTierDisplayName, TIER_COMPARISON } from "@/lib/tier";
import { useRoutingRules } from "@/hooks/use-routing-rules";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface TierGateProps {
  children: ReactNode;
}

export function TierGate({ children }: TierGateProps) {
  const { user } = useAuth();
  const { data: rules } = useRoutingRules();

  const tier = user?.subscription_tier || "free";
  const limit = getTierLimit(tier);
  const count = rules?.length ?? 0;

  if (count >= limit) {
    // Find next tier
    const tierIndex = TIER_COMPARISON.findIndex((t) => t.tier === tier);
    const nextTier = tierIndex >= 0 && tierIndex < TIER_COMPARISON.length - 1
      ? TIER_COMPARISON[tierIndex + 1]
      : null;

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
              {nextTier && (
                <> Upgrade to {nextTier.name} for up to {nextTier.maxRules} rules ({nextTier.price}).</>
              )}
            </p>
            <Button asChild size="sm" className="h-7 text-xs">
              <Link to="/settings">
                Upgrade
                <ArrowRight className="ml-1 h-3 w-3" />
              </Link>
            </Button>
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
  const count = rules?.length ?? 0;

  if (count < limit) return null;

  return (
    <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3">
      <div className="flex items-center gap-2">
        <ShieldAlert className="h-3.5 w-3.5 text-amber-500 shrink-0" />
        <p className="text-xs text-amber-700 dark:text-amber-300">
          You've reached the {getTierDisplayName(tier)} limit of {limit} rule{limit !== 1 ? "s" : ""}.{" "}
          <Link to="/settings" className="underline font-medium">
            Upgrade your plan
          </Link>{" "}
          to add more.
        </p>
      </div>
    </div>
  );
}
