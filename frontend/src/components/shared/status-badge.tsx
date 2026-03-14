import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type StatusType =
  | "connected"
  | "disconnected"
  | "active"
  | "inactive"
  | "success"
  | "failed"
  | "ignored";

const statusConfig: Record<
  StatusType,
  { label: string; className: string; dotColor: string }
> = {
  connected: {
    label: "Connected",
    className: "bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400",
    dotColor: "bg-emerald-500",
  },
  disconnected: {
    label: "Disconnected",
    className: "bg-rose-500/10 text-rose-600 dark:bg-rose-500/15 dark:text-rose-400",
    dotColor: "bg-rose-500",
  },
  active: {
    label: "Active",
    className: "bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400",
    dotColor: "bg-emerald-500",
  },
  inactive: {
    label: "Inactive",
    className: "bg-zinc-500/10 text-zinc-500 dark:bg-zinc-500/15 dark:text-zinc-400",
    dotColor: "bg-zinc-400",
  },
  success: {
    label: "Success",
    className: "bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400",
    dotColor: "bg-emerald-500",
  },
  failed: {
    label: "Failed",
    className: "bg-rose-500/10 text-rose-600 dark:bg-rose-500/15 dark:text-rose-400",
    dotColor: "bg-rose-500",
  },
  ignored: {
    label: "Ignored",
    className: "bg-amber-500/10 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400",
    dotColor: "bg-amber-500",
  },
};

interface StatusBadgeProps {
  status: StatusType;
  variant?: "badge" | "dot";
}

export function StatusBadge({ status, variant = "badge" }: StatusBadgeProps) {
  const config = statusConfig[status] ?? statusConfig.inactive;

  if (variant === "dot") {
    return (
      <span className="inline-flex items-center gap-1.5">
        <span className={cn("h-1.5 w-1.5 rounded-full", config.dotColor)} />
        <span className="text-xs text-muted-foreground">{config.label}</span>
      </span>
    );
  }

  return (
    <Badge variant="secondary" className={cn("text-[11px] font-medium rounded-sm px-1.5 py-0", config.className)}>
      {config.label}
    </Badge>
  );
}
