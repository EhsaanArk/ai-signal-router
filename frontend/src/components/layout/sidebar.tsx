import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  MessageSquare,
  Route,
  ScrollText,
  Settings,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useAuth } from "@/contexts/auth-context";
import { getTierDisplayName, getTierLimit } from "@/lib/tier";
import { useRoutingRules } from "@/hooks/use-routing-rules";
import { useTelegramStatus } from "@/hooks/use-telegram";
import { cn } from "@/lib/utils";

const navItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/telegram", label: "Telegram", icon: MessageSquare },
  { path: "/routing-rules", label: "Signal Routes", icon: Route },
  { path: "/logs", label: "Signal Logs", icon: ScrollText },
  { path: "/settings", label: "Settings", icon: Settings },
];

const tierColors: Record<string, string> = {
  free: "text-zinc-400",
  starter: "text-blue-400",
  pro: "text-violet-400",
  elite: "text-amber-400",
};

export function Sidebar({ className, onNavClick }: { className?: string; onNavClick?: () => void }) {
  const location = useLocation();
  const { user } = useAuth();
  const { data: rules } = useRoutingRules();
  const { data: telegramStatus } = useTelegramStatus();

  const tier = user?.subscription_tier || "free";
  const ruleCount = rules?.length ?? 0;
  const tierLimit = getTierLimit(tier);
  const connected = telegramStatus?.connected ?? false;

  return (
    <aside
      className={cn(
        "flex h-full w-14 flex-col border-r bg-sidebar text-sidebar-foreground",
        className
      )}
    >
      {/* Logo */}
      <div className="flex h-14 items-center justify-center border-b border-sidebar-border">
        <span className="text-lg font-bold text-primary">SC</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 flex flex-col items-center gap-1 py-3">
        {navItems.map((item) => {
          const isActive =
            item.path === "/"
              ? location.pathname === "/"
              : location.pathname.startsWith(item.path);
          return (
            <Tooltip key={item.path} delayDuration={0}>
              <TooltipTrigger asChild>
                <Link
                  to={item.path}
                  onClick={onNavClick}
                  className={cn(
                    "relative flex h-10 w-10 items-center justify-center rounded-md transition-colors",
                    isActive
                      ? "bg-sidebar-accent text-primary"
                      : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
                  )}
                >
                  {isActive && (
                    <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r-full bg-primary" />
                  )}
                  <item.icon className="h-[18px] w-[18px]" />
                </Link>
              </TooltipTrigger>
              <TooltipContent side="right" sideOffset={8}>
                {item.label}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </nav>

      {/* Bottom: Tier + Connection */}
      <div className="flex flex-col items-center gap-3 border-t border-sidebar-border py-3">
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <span className={cn("text-[10px] font-bold uppercase tracking-wider cursor-default", tierColors[tier] || "text-zinc-400")}>
              {getTierDisplayName(tier).slice(0, 3)}
            </span>
          </TooltipTrigger>
          <TooltipContent side="right" sideOffset={8}>
            {getTierDisplayName(tier)} — {ruleCount}/{tierLimit} routes
          </TooltipContent>
        </Tooltip>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                connected ? "bg-emerald-500" : "bg-rose-500 animate-pulse"
              )}
            />
          </TooltipTrigger>
          <TooltipContent side="right" sideOffset={8}>
            Telegram: {connected ? "Connected" : "Disconnected"}
          </TooltipContent>
        </Tooltip>
      </div>
    </aside>
  );
}
