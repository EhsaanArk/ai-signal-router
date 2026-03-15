import { useLocation } from "react-router-dom";
import { Menu, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/hooks/use-theme";
import { useAuth } from "@/contexts/auth-context";

interface HeaderProps {
  onMenuClick: () => void;
}

const routeNames: Record<string, string> = {
  "/": "Dashboard",
  "/telegram": "Telegram",
  "/routing-rules": "Signal Routes",
  "/routing-rules/new": "New Route",
  "/logs": "Signal Logs",
  "/settings": "Settings",
};

export function Header({ onMenuClick }: HeaderProps) {
  const { theme, toggleTheme } = useTheme();
  const { user } = useAuth();
  const location = useLocation();

  const pageName =
    routeNames[location.pathname] ||
    (location.pathname.includes("/routing-rules/") && location.pathname.includes("/edit")
      ? "Edit Route"
      : "");

  return (
    <header className="flex h-12 items-center justify-between border-b px-4">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden h-8 w-8"
          onClick={onMenuClick}
          aria-label="Open menu"
        >
          <Menu className="h-4 w-4" />
        </Button>
        <span className="text-sm font-medium">{pageName}</span>
      </div>
      <div className="flex items-center gap-1">
        {user?.email && (
          <span className="hidden md:inline text-xs text-muted-foreground mr-2">
            {user.email}
          </span>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </Button>
      </div>
    </header>
  );
}
