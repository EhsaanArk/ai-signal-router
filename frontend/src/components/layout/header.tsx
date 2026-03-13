import { Menu, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useTheme } from "@/hooks/use-theme";
import { useTelegramStatus } from "@/hooks/use-telegram";

interface HeaderProps {
  onMenuClick: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  const { theme, toggleTheme } = useTheme();
  const { data: telegramStatus } = useTelegramStatus();

  const connected = telegramStatus?.connected ?? false;

  return (
    <header className="flex h-14 items-center justify-between border-b px-4 lg:justify-end">
      <Button
        variant="ghost"
        size="icon"
        className="lg:hidden"
        onClick={onMenuClick}
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </Button>
      <div className="flex items-center gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="flex items-center justify-center h-9 w-9">
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  connected ? "bg-green-500" : "bg-red-500"
                }`}
              />
            </span>
          </TooltipTrigger>
          <TooltipContent>
            Telegram: {connected ? "Connected" : "Disconnected"}
          </TooltipContent>
        </Tooltip>
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
          )}
        </Button>
      </div>
    </header>
  );
}
