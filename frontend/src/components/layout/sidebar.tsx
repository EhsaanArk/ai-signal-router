import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  MessageSquare,
  Route,
  ScrollText,
  Settings,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/contexts/auth-context";
import { getTierDisplayName, getTierLimit } from "@/lib/tier";
import { useRoutingRules } from "@/hooks/use-routing-rules";
import { cn } from "@/lib/utils";
import { APP_NAME } from "@/lib/constants";

const navItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/telegram", label: "Telegram", icon: MessageSquare },
  { path: "/routing-rules", label: "Routing Rules", icon: Route },
  { path: "/logs", label: "Signal Logs", icon: ScrollText },
  { path: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar({ className, onNavClick }: { className?: string; onNavClick?: () => void }) {
  const location = useLocation();
  const { user } = useAuth();
  const { data: rules } = useRoutingRules();

  const tier = user?.subscription_tier || "free";
  const ruleCount = rules?.length ?? 0;
  const tierLimit = getTierLimit(tier);

  return (
    <aside
      className={cn(
        "flex h-full w-60 flex-col border-r bg-sidebar text-sidebar-foreground",
        className
      )}
    >
      <div className="flex h-14 items-center px-4 font-semibold">
        {APP_NAME}
      </div>
      <Separator />
      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => {
          const isActive =
            item.path === "/"
              ? location.pathname === "/"
              : location.pathname.startsWith(item.path);
          return (
            <Link
              key={item.path}
              to={item.path}
              onClick={onNavClick}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <Separator />
      <div className="p-4 space-y-2">
        <div className="flex items-center justify-between">
          <Badge variant="secondary">{getTierDisplayName(tier)}</Badge>
          <span className="text-xs text-muted-foreground">
            {ruleCount}/{tierLimit} rules
          </span>
        </div>
      </div>
    </aside>
  );
}
