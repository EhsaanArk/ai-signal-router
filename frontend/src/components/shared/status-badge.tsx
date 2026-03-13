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
  { label: string; className: string }
> = {
  connected: {
    label: "Connected",
    className: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  },
  disconnected: {
    label: "Disconnected",
    className: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  },
  active: {
    label: "Active",
    className: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  },
  inactive: {
    label: "Inactive",
    className: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  },
  success: {
    label: "Success",
    className: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  },
  failed: {
    label: "Failed",
    className: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  },
  ignored: {
    label: "Ignored",
    className: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  },
};

export function StatusBadge({ status }: { status: StatusType }) {
  const config = statusConfig[status] ?? statusConfig.inactive;
  return (
    <Badge variant="secondary" className={cn("font-medium", config.className)}>
      {config.label}
    </Badge>
  );
}
