import { Link, useParams } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/shared/status-badge";
import { useAdminUserDetail } from "@/hooks/use-admin";
import { usePageTitle } from "@/hooks/use-page-title";

export function AdminUserDetailPage() {
  usePageTitle("Admin - User Detail");
  const { id } = useParams<{ id: string }>();
  const { data: user, isLoading } = useAdminUserDetail(id || "");

  if (isLoading) {
    return (
      <div className="space-y-4 max-w-3xl">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (!user) {
    return <p className="text-sm text-muted-foreground">User not found.</p>;
  }

  return (
    <div className="space-y-4 max-w-3xl">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-xs text-muted-foreground">
        <Link to="/admin/users" className="hover:text-foreground transition-colors">
          Users
        </Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-foreground">{user.email}</span>
      </nav>

      {/* User Info */}
      <Card>
        <CardHeader className="pb-3 pt-4 px-4">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            {user.email}
            {user.is_admin && (
              <span className="text-[9px] bg-violet-500/10 text-violet-500 px-1.5 py-0.5 rounded">admin</span>
            )}
            {user.is_disabled && (
              <span className="text-[9px] bg-rose-500/10 text-rose-500 px-1.5 py-0.5 rounded">disabled</span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div>
              <p className="text-muted-foreground">Tier</p>
              <p className="font-medium capitalize">{user.subscription_tier}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Routes</p>
              <p className="font-medium font-tabular">{user.rule_count}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Signals</p>
              <p className="font-medium font-tabular">{user.signal_count}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Telegram</p>
              <p className="font-medium">{user.telegram_connected ? "Connected" : "Not connected"}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Created</p>
              <p className="font-medium">
                {new Date(user.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Routing Rules */}
      <Card>
        <CardHeader className="pb-3 pt-4 px-4">
          <CardTitle className="text-xs font-medium">Routing Rules ({user.routing_rules.length})</CardTitle>
        </CardHeader>
        <CardContent className="px-0 pb-0">
          {user.routing_rules.length === 0 ? (
            <p className="text-xs text-muted-foreground px-4 pb-4">No routing rules</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-[10px]">Name / Channel</TableHead>
                  <TableHead className="text-[10px]">Type</TableHead>
                  <TableHead className="text-[10px]">Version</TableHead>
                  <TableHead className="text-[10px]">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {user.routing_rules.map((rule) => (
                  <TableRow key={rule.id}>
                    <TableCell className="text-xs">
                      {rule.rule_name || rule.source_channel_name || rule.source_channel_id}
                    </TableCell>
                    <TableCell className="text-xs capitalize">{rule.destination_type.replace(/_/g, " ")}</TableCell>
                    <TableCell className="text-xs">{rule.payload_version}</TableCell>
                    <TableCell>
                      <StatusBadge status={rule.is_active ? "active" : "inactive"} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Recent Signals */}
      <Card>
        <CardHeader className="pb-3 pt-4 px-4">
          <CardTitle className="text-xs font-medium">Recent Signals (last 20)</CardTitle>
        </CardHeader>
        <CardContent className="px-0 pb-0">
          {user.recent_signals.length === 0 ? (
            <p className="text-xs text-muted-foreground px-4 pb-4">No signals yet</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-[10px]">Status</TableHead>
                  <TableHead className="text-[10px]">Time</TableHead>
                  <TableHead className="text-[10px]">Channel</TableHead>
                  <TableHead className="text-[10px]">Message</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {user.recent_signals.map((sig) => (
                  <TableRow key={sig.id}>
                    <TableCell>
                      <StatusBadge status={sig.status as "success" | "failed" | "ignored"} />
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(sig.processed_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </TableCell>
                    <TableCell className="text-xs font-mono">{sig.channel_id || "—"}</TableCell>
                    <TableCell className="text-xs max-w-[200px] truncate">{sig.raw_message}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Notification Preferences */}
      <Card>
        <CardHeader className="pb-3 pt-4 px-4">
          <CardTitle className="text-xs font-medium">Notification Preferences</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <pre className="text-[10px] font-mono bg-muted/50 rounded p-2 overflow-x-auto">
            {JSON.stringify(user.notification_preferences, null, 2)}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}
