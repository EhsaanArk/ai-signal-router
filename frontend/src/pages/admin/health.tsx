import { Activity, Users, Radio, Route, Smartphone, TrendingUp, Calendar } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminHealth } from "@/hooks/use-admin";
import { usePageTitle } from "@/hooks/use-page-title";
import { cn } from "@/lib/utils";

export function AdminHealthPage() {
  usePageTitle("System Health");
  const { data, isLoading } = useAdminHealth();

  const stats = [
    { label: "Total Users", value: data?.total_users, icon: Users, color: "text-blue-500" },
    { label: "Active Users (7d)", value: data?.active_users_7d, icon: TrendingUp, color: "text-emerald-500" },
    { label: "Signals Today", value: data?.signals_today, icon: Radio, color: "text-violet-500" },
    { label: "Signals This Week", value: data?.signals_this_week, icon: Calendar, color: "text-indigo-500" },
    {
      label: "Success Rate (24h)",
      value: data?.success_rate_24h != null ? `${data.success_rate_24h}%` : undefined,
      icon: Activity,
      color: data?.success_rate_24h != null
        ? data.success_rate_24h >= 90 ? "text-emerald-500"
        : data.success_rate_24h >= 70 ? "text-amber-500"
        : "text-rose-500"
        : "text-muted-foreground",
    },
    { label: "Active Routes", value: data?.active_routing_rules, icon: Route, color: "text-orange-500" },
    { label: "TG Sessions", value: data?.active_telegram_sessions, icon: Smartphone, color: "text-cyan-500" },
  ];

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-medium">System Health</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <CardHeader className="pb-2 pt-3 px-4">
              <CardTitle className="text-[10px] font-medium text-muted-foreground flex items-center gap-1.5">
                <stat.icon className={cn("h-3 w-3", stat.color)} />
                {stat.label}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3">
              {isLoading ? (
                <Skeleton className="h-7 w-16" />
              ) : (
                <p className="text-xl font-bold font-tabular">{stat.value ?? "—"}</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

export default AdminHealthPage;
