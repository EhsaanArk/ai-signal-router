import { useNavigate } from "react-router-dom";
import { Plus, Route } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { TierGate } from "@/components/shared/tier-gate";
import { RoutingRulesTable } from "@/components/tables/routing-rules-table";
import { useRoutingRules } from "@/hooks/use-routing-rules";
import { useAuth } from "@/contexts/auth-context";
import { getTierLimit } from "@/lib/tier";
import { usePageTitle } from "@/hooks/use-page-title";

export function RoutingRulesPage() {
  usePageTitle("Signal Routes");
  const navigate = useNavigate();
  const { data: rules, isLoading } = useRoutingRules();
  const { user } = useAuth();

  const tier = user?.subscription_tier || "free";
  const limit = getTierLimit(tier);
  const atLimit = (rules?.length ?? 0) >= limit;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-medium">Signal Routes</h1>
          {rules && (
            <span className="text-[11px] text-muted-foreground font-tabular">
              {rules.length}/{limit}
            </span>
          )}
        </div>
        {!atLimit && (
          <Button size="sm" className="h-7 text-xs" onClick={() => navigate("/routing-rules/new")}>
            <Plus className="mr-1 h-3 w-3" />
            New Route
          </Button>
        )}
      </div>

      {atLimit && <TierGate><span /></TierGate>}

      {isLoading ? (
        <div className="space-y-1">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : !rules?.length ? (
        <EmptyState
          icon={Route}
          title="No signal routes yet"
          description="Create your first route to start forwarding trading signals from Telegram to your SageMaster account."
          actionLabel="Create Route"
          onAction={() => navigate("/routing-rules/new")}
        />
      ) : (
        <RoutingRulesTable rules={rules} />
      )}
    </div>
  );
}
