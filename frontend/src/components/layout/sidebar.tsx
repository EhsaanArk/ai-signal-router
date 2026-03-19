import { Link, useLocation } from "react-router-dom";
import {
  Activity,
  BookOpen,
  Brain,
  LayoutDashboard,
  MessageSquare,
  Radio,
  Route,
  ScrollText,
  Settings,
  Users,
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

/** Map route paths to their dynamic import functions for prefetching on hover */
const routePrefetchMap: Record<string, () => Promise<unknown>> = {
  "/": () => import("../../pages/dashboard"),
  "/telegram": () => import("../../pages/telegram"),
  "/routing-rules": () => import("../../pages/routing-rules"),
  "/logs": () => import("../../pages/logs"),
  "/settings": () => import("../../pages/settings"),
  "/admin/health": () => import("../../pages/admin/health"),
  "/admin/users": () => import("../../pages/admin/users"),
  "/admin/signals": () => import("../../pages/admin/signals"),
  "/admin/system-rules": () => import("../../pages/admin/system-rules"),
  "/admin/parser": () => import("../../pages/admin/parser"),
  "/admin/settings": () => import("../../pages/admin/settings"),
};

function prefetchRoute(path: string) {
  const loader = routePrefetchMap[path];
  if (loader) loader().catch(() => { /* chunk prefetch failed — no-op */ });
}

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
      <div className="flex h-14 flex-col items-center justify-center border-b border-sidebar-border gap-0.5 group cursor-pointer">
        <img src="/logo.svg" alt="Sage Radar AI" className="h-7 w-7 transition-transform duration-200 group-hover:scale-110 group-hover:rotate-12" />
        <span className="text-[7px] font-bold uppercase tracking-wider px-1 py-px rounded-full bg-amber-500/15 text-amber-500 border border-amber-500/20 transition-colors duration-200 group-hover:text-primary">Beta</span>
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
                  onMouseEnter={() => prefetchRoute(item.path)}
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

      {/* Admin Nav */}
      {user?.is_admin && (
        <div className="flex flex-col items-center gap-1 border-t border-sidebar-border py-2 overflow-y-auto">
          <span className="text-[8px] font-bold uppercase tracking-widest text-muted-foreground/50 mb-0.5">
            Admin
          </span>
          {[
            { path: "/admin/health", label: "System Health", icon: Activity },
            { path: "/admin/users", label: "Users", icon: Users },
            { path: "/admin/signals", label: "All Signals", icon: Radio },
            { path: "/admin/system-rules", label: "System Rules", icon: BookOpen },
            { path: "/admin/parser", label: "AI Parser", icon: Brain },
            { path: "/admin/settings", label: "Settings", icon: Settings },
          ].map((item) => {
            const isActive = location.pathname.startsWith(item.path);
            return (
              <Tooltip key={item.path} delayDuration={0}>
                <TooltipTrigger asChild>
                  <Link
                    to={item.path}
                    onClick={onNavClick}
                    onMouseEnter={() => prefetchRoute(item.path)}
                    className={cn(
                      "relative flex h-9 w-9 items-center justify-center rounded-md transition-colors",
                      isActive
                        ? "bg-sidebar-accent text-primary"
                        : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
                    )}
                  >
                    <item.icon className="h-4 w-4" />
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="right" sideOffset={8}>
                  {item.label}
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      )}

      {/* Bottom: Tier + Connection */}
      <div className="flex flex-col items-center gap-3 border-t border-sidebar-border py-3">
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <span className={cn("text-[10px] font-bold uppercase tracking-wider cursor-default", tierColors[tier] || "text-zinc-400")}>
              {({ free: "FREE", starter: "STR", pro: "PRO", elite: "ELT" }[tier]) || tier.slice(0, 3).toUpperCase()}
            </span>
          </TooltipTrigger>
          <TooltipContent side="right" sideOffset={8}>
            {getTierDisplayName(tier)} — {ruleCount}/{tierLimit} routes
          </TooltipContent>
        </Tooltip>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            {connected ? (
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
            ) : (
              <Link to="/telegram" className="h-2 w-2 rounded-full bg-rose-500 animate-pulse block" />
            )}
          </TooltipTrigger>
          <TooltipContent side="right" sideOffset={8}>
            {connected ? "Telegram: Connected" : "Telegram disconnected \u2014 click to reconnect"}
          </TooltipContent>
        </Tooltip>
      </div>
    </aside>
  );
}
