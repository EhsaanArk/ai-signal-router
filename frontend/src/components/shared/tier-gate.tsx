import type { ReactNode } from "react";
import { useAuth } from "@/contexts/auth-context";
import { getTierLimit, getTierDisplayName } from "@/lib/tier";
import { useRoutingRules } from "@/hooks/use-routing-rules";
import { Card, CardContent } from "@/components/ui/card";
import { ShieldAlert } from "lucide-react";

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
    return (
      <Card className="border-amber-200 dark:border-amber-800">
        <CardContent className="flex items-center gap-3 pt-6">
          <ShieldAlert className="h-5 w-5 text-amber-500" />
          <div>
            <p className="text-sm font-medium">
              Rule limit reached ({count}/{limit})
            </p>
            <p className="text-xs text-muted-foreground">
              Your {getTierDisplayName(tier)} plan allows up to {limit} routing
              rule(s). Upgrade to add more.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return <>{children}</>;
}
