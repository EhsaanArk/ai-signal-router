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
  usePageTitle("Routing Rules");
  const navigate = useNavigate();
  const { data: rules, isLoading } = useRoutingRules();
  const { user } = useAuth();

  const tier = user?.subscription_tier || "free";
  const limit = getTierLimit(tier);
  const atLimit = (rules?.length ?? 0) >= limit;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Routing Rules</h1>
        {!atLimit && (
          <Button onClick={() => navigate("/routing-rules/new")}>
            <Plus className="mr-2 h-4 w-4" />
            New Rule
          </Button>
        )}
      </div>

      {atLimit && <TierGate><span /></TierGate>}

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : !rules?.length ? (
        <EmptyState
          icon={Route}
          title="No routing rules"
          description="Create your first routing rule to start forwarding signals to your webhook."
          actionLabel="Create Rule"
          onAction={() => navigate("/routing-rules/new")}
        />
      ) : (
        <RoutingRulesTable rules={rules} />
      )}
    </div>
  );
}
