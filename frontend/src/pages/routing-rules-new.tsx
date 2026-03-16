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
  usePageTitle("New Route");
  const navigate = useNavigate();

  return (
    <div className="max-w-xl">
      <Card>
        <CardHeader className="pb-3 pt-4 px-4">
          <CardTitle className="text-sm font-medium">Create Route</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <RoutingRuleWizard onComplete={() => navigate("/routing-rules")} />
        </CardContent>
      </Card>
    </div>
  );
}

export default RoutingRulesNewPage;
