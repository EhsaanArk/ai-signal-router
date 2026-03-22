import { Copy, Check } from "lucide-react";
import { useState } from "react";
import { Switch } from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { ActionDefinition } from "@/lib/action-definitions";

interface ActionRowProps {
  action: ActionDefinition;
  isEnabled: boolean;
  onToggle?: (key: string) => void;
  /** When true, copy icon appears next to the example. */
  showCopy?: boolean;
  /** When true, entry actions show a disabled "always on" switch. */
  readOnly?: boolean;
}

export function ActionRow({
  action,
  isEnabled,
  onToggle,
  showCopy = false,
  readOnly = false,
}: ActionRowProps) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    // Strip surrounding quotes from the example text
    const text = action.example.replace(/^"|"$/g, "").split('", "')[0];
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2.5 transition-colors",
        isEnabled
          ? "border-border"
          : "border-border/50 bg-muted/30 opacity-60",
      )}
    >
      <div className="flex items-start gap-3">
        {/* Toggle */}
        <div className="pt-0.5">
          {action.isEntry || readOnly ? (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div>
                    <Switch checked disabled className="opacity-50" />
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">Entry actions are always enabled</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          ) : (
            <Switch
              checked={isEnabled}
              onCheckedChange={() => onToggle?.(action.key)}
              aria-label={`${action.label}: ${isEnabled ? "enabled" : "disabled"}`}
            />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium">{action.label}</span>
            <span className="text-[10px] text-muted-foreground">
              {action.description}
            </span>
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <p className="text-[10px] text-muted-foreground">
              e.g. {action.example}
            </p>
            {showCopy && (
              <button
                type="button"
                onClick={handleCopy}
                className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                aria-label={`Copy example: ${action.label}`}
              >
                {copied ? (
                  <Check className="h-3 w-3 text-emerald-500" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
