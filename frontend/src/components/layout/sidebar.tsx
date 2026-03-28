import { Link, useLocation } from "react-router-dom";
import {
  Activity,
  Bookmark,
  BookOpen,
  Brain,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,

  Radio,
  Route,
  ScrollText,
  Settings,
  Store,
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
  "/connectors": () => import("../../pages/connectors"),
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
  "/marketplace": () => import("../../pages/marketplace"),
  "/dashboard/subscriptions": () => import("../../pages/marketplace-subscriptions"),
  "/admin/marketplace": () => import("../../pages/admin/marketplace"),
};

function prefetchRoute(path: string) {
  const loader = routePrefetchMap[path];
  if (loader) loader().catch(() => { /* chunk prefetch failed — no-op */ });
}

const marketplaceEnabled = import.meta.env.VITE_MARKETPLACE_ENABLED === "true";

const baseNavItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/connectors", label: "Connectors", icon: Radio },
  { path: "/routing-rules", label: "Signal Routes", icon: Route },
];

const marketplaceNavItems = [
  { path: "/marketplace", label: "Marketplace", icon: Store },
  { path: "/dashboard/subscriptions", label: "My Subs", icon: Bookmark },
];

const trailingNavItems = [
  { path: "/logs", label: "Signal Logs", icon: ScrollText },
  { path: "/settings", label: "Settings", icon: Settings },
];

const navItems = marketplaceEnabled
  ? [...baseNavItems, ...marketplaceNavItems, ...trailingNavItems]
  : [...baseNavItems, ...trailingNavItems];

const tierColors: Record<string, string> = {
  free: "text-zinc-400",
  starter: "text-blue-400",
  pro: "text-violet-400",
  elite: "text-amber-400",
};

interface SidebarProps {
  className?: string;
  onNavClick?: () => void;
  collapsed: boolean;
  onToggle: () => void;
}

function NavLink({
  item,
  isActive,
  collapsed,
  onNavClick,
  size = "md",
}: {
  item: { path: string; label: string; icon: React.ComponentType<{ className?: string }> };
  isActive: boolean;
  collapsed: boolean;
  onNavClick?: () => void;
  size?: "sm" | "md";
}) {
  const h = size === "sm" ? "h-9" : "h-10";
  const iconSize = size === "sm" ? "h-4 w-4" : "h-[18px] w-[18px]";

  const link = (
    <Link
      to={item.path}
      onClick={onNavClick}
      onMouseEnter={() => prefetchRoute(item.path)}
      className={cn(
        "relative flex items-center rounded-md transition-colors",
        h,
        collapsed ? "w-10 justify-center" : "w-full gap-3 px-3",
        isActive
          ? "bg-sidebar-accent text-primary"
          : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
      )}
    >
      {isActive && (
        <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r-full bg-primary" />
      )}
      <item.icon className={cn(iconSize, "shrink-0")} />
      {!collapsed && (
        <span className="text-sm truncate">{item.label}</span>
      )}
    </Link>
  );

  if (collapsed) {
    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>{link}</TooltipTrigger>
        <TooltipContent side="right" sideOffset={8}>
          {item.label}
        </TooltipContent>
      </Tooltip>
    );
  }

  return link;
}

export function Sidebar({ className, onNavClick, collapsed, onToggle }: SidebarProps) {
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
        "flex h-full flex-col border-r bg-sidebar text-sidebar-foreground transition-[width] duration-200",
        collapsed ? "w-14" : "w-52",
        className
      )}
    >
      {/* Logo + collapse toggle */}
      <div className={cn(
        "flex h-14 items-center border-b border-sidebar-border",
        collapsed ? "justify-center px-0" : "justify-between px-3"
      )}>
        <div className={cn("flex items-center gap-2", collapsed && "flex-col gap-0.5")}>
          <img src="/logo.svg" alt="Sage Radar AI" className="h-7 w-7" />
          {!collapsed && (
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-semibold tracking-tight">Sage Radar</span>
              <span className="text-[7px] font-bold uppercase tracking-wider px-1 py-px rounded-full bg-amber-500/15 text-amber-500 border border-amber-500/20">Beta</span>
            </div>
          )}
          {collapsed && (
            <span className="text-[7px] font-bold uppercase tracking-wider px-1 py-px rounded-full bg-amber-500/15 text-amber-500 border border-amber-500/20">Beta</span>
          )}
        </div>
        {!collapsed && (
          <button
            type="button"
            onClick={onToggle}
            className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-sidebar-accent/50 transition-colors"
            aria-label="Collapse sidebar"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Expand button when collapsed */}
      {collapsed && (
        <div className="flex justify-center py-2">
          <button
            type="button"
            onClick={onToggle}
            className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-sidebar-accent/50 transition-colors"
            aria-label="Expand sidebar"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Nav */}
      <nav className={cn("flex-1 flex flex-col gap-1 py-3", collapsed ? "items-center" : "px-2")}>
        {navItems.map((item) => {
          const isActive =
            item.path === "/"
              ? location.pathname === "/"
              : location.pathname.startsWith(item.path);
          return (
            <NavLink
              key={item.path}
              item={item}
              isActive={isActive}
              collapsed={collapsed}
              onNavClick={onNavClick}
            />
          );
        })}
      </nav>

      {/* Admin Nav */}
      {user?.is_admin && (
        <div className={cn(
          "flex flex-col gap-1 border-t border-sidebar-border py-2 overflow-y-auto",
          collapsed ? "items-center" : "px-2"
        )}>
          <span className={cn(
            "text-[8px] font-bold uppercase tracking-widest text-muted-foreground/50 mb-0.5",
            collapsed ? "text-center" : "px-3"
          )}>
            Admin
          </span>
          {[
            { path: "/admin/health", label: "System Health", icon: Activity },
            { path: "/admin/users", label: "Users", icon: Users },
            { path: "/admin/signals", label: "All Signals", icon: Radio },
            { path: "/admin/system-rules", label: "System Rules", icon: BookOpen },
            { path: "/admin/parser", label: "Sage Intelligence", icon: Brain },
            ...(marketplaceEnabled ? [{ path: "/admin/marketplace", label: "Marketplace", icon: Store }] : []),
            { path: "/admin/settings", label: "Settings", icon: Settings },
          ].map((item) => {
            const isActive = location.pathname.startsWith(item.path);
            return (
              <NavLink
                key={item.path}
                item={item}
                isActive={isActive}
                collapsed={collapsed}
                onNavClick={onNavClick}
                size="sm"
              />
            );
          })}
        </div>
      )}

      {/* Bottom: Tier + Connection */}
      <div className={cn(
        "flex items-center gap-3 border-t border-sidebar-border py-3",
        collapsed ? "flex-col" : "px-3"
      )}>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <span className={cn("text-[10px] font-bold uppercase tracking-wider cursor-default", tierColors[tier] || "text-zinc-400")}>
              {collapsed
                ? ({ free: "FREE", starter: "STR", pro: "PRO", elite: "ELT" }[tier]) || tier.slice(0, 3).toUpperCase()
                : getTierDisplayName(tier)
              }
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
        {!collapsed && (
          <span className="text-[10px] text-muted-foreground">
            {connected ? "Connected" : "Disconnected"}
          </span>
        )}
      </div>
    </aside>
  );
}
