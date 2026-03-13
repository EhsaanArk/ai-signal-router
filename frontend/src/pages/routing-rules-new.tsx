import { useNavigate } from "react-router-dom";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { RoutingRuleWizard } from "@/components/forms/routing-rule-wizard";
import { usePageTitle } from "@/hooks/use-page-title";

export function RoutingRulesNewPage() {
  usePageTitle("New Rule");
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Create Routing Rule</h1>
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>New Rule</CardTitle>
        </CardHeader>
        <CardContent>
          <RoutingRuleWizard onComplete={() => navigate("/routing-rules")} />
        </CardContent>
      </Card>
    </div>
  );
}
