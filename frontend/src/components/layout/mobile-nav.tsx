import { Link, useLocation } from "react-router-dom";
import {
  Activity,
  BookOpen,
  LayoutDashboard,
  MessageSquare,
  Radio,
  Route,
  ScrollText,
  Settings,
  Users,
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useAuth } from "@/contexts/auth-context";
import { useTelegramStatus } from "@/hooks/use-telegram";
import { getTierDisplayName } from "@/lib/tier";
import { cn } from "@/lib/utils";

const navItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/telegram", label: "Telegram", icon: MessageSquare },
  { path: "/routing-rules", label: "Signal Routes", icon: Route },
  { path: "/logs", label: "Signal Logs", icon: ScrollText },
  { path: "/settings", label: "Settings", icon: Settings },
];

interface MobileNavProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MobileNav({ open, onOpenChange }: MobileNavProps) {
  const location = useLocation();
  const { user } = useAuth();
  const { data: telegramStatus } = useTelegramStatus();
  const tier = user?.subscription_tier || "free";
  const connected = telegramStatus?.connected ?? false;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-56 p-0">
        <SheetHeader className="sr-only">
          <SheetTitle>Navigation</SheetTitle>
        </SheetHeader>
        <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
          {/* Logo */}
          <div className="flex h-12 items-center gap-2 px-4 border-b border-sidebar-border group">
            <img src="/logo.svg" alt="Sage Radar AI" className="h-6 w-6 transition-transform duration-200 group-hover:scale-110 group-hover:rotate-12" />
            <span className="text-sm font-bold text-primary transition-colors duration-200 group-hover:text-primary">Sage Radar AI</span>
            <span className="text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-500 border border-amber-500/20 transition-colors duration-200 group-hover:text-primary">Beta</span>
          </div>

          {/* Nav */}
          <nav className="flex-1 space-y-0.5 p-2">
            {navItems.map((item) => {
              const isActive =
                item.path === "/"
                  ? location.pathname === "/"
                  : location.pathname.startsWith(item.path);
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => onOpenChange(false)}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                    isActive
                      ? "bg-sidebar-accent text-primary font-medium"
                      : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
            {/* Admin section */}
            {user?.is_admin && (
              <>
                <div className="my-1 border-t border-sidebar-border" />
                <p className="px-3 pt-1 pb-0.5 text-[9px] font-bold uppercase tracking-widest text-muted-foreground/50">
                  Admin
                </p>
                {[
                  { path: "/admin/health", label: "System Health", icon: Activity },
                  { path: "/admin/users", label: "Users", icon: Users },
                  { path: "/admin/signals", label: "All Signals", icon: Radio },
                  { path: "/admin/system-rules", label: "System Rules", icon: BookOpen },
                ].map((item) => {
                  const isActive = location.pathname.startsWith(item.path);
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      onClick={() => onOpenChange(false)}
                      className={cn(
                        "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                        isActive
                          ? "bg-sidebar-accent text-primary font-medium"
                          : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
                      )}
                    >
                      <item.icon className="h-4 w-4" />
                      {item.label}
                    </Link>
                  );
                })}
              </>
            )}
          </nav>

          {/* Bottom */}
          <div className="flex items-center justify-between border-t border-sidebar-border px-4 py-3">
            <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              {getTierDisplayName(tier)}
            </span>
            <span className={cn(
              "h-2 w-2 rounded-full",
              connected ? "bg-emerald-500" : "bg-rose-500 animate-pulse"
            )} />
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
