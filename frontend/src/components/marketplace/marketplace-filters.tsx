import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type { MarketplaceSort, MarketplaceFilter } from "@/types/marketplace";

const SORT_OPTIONS: { value: MarketplaceSort; label: string }[] = [
  { value: "win_rate", label: "Win Rate" },
  { value: "pnl", label: "P&L" },
  { value: "signals", label: "Signals" },
  { value: "subscribers", label: "Subscribers" },
];

const FILTER_OPTIONS: { value: MarketplaceFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "forex", label: "Forex" },
  { value: "crypto", label: "Crypto" },
];

interface MarketplaceFiltersProps {
  sort: MarketplaceSort;
  filter: MarketplaceFilter;
  onSortChange: (sort: MarketplaceSort) => void;
  onFilterChange: (filter: MarketplaceFilter) => void;
}

export function MarketplaceFilters({
  sort,
  filter,
  onSortChange,
  onFilterChange,
}: MarketplaceFiltersProps) {
  return (
    <div className="flex items-center gap-3">
      {/* Sort dropdown */}
      <Select value={sort} onValueChange={(v) => onSortChange(v as MarketplaceSort)}>
        <SelectTrigger className="h-8 w-[140px] text-xs">
          <SelectValue placeholder="Sort by" />
        </SelectTrigger>
        <SelectContent>
          {SORT_OPTIONS.map((opt) => (
            <SelectItem key={opt.value} value={opt.value} className="text-xs">
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Filter pills */}
      <div className="flex items-center gap-1 rounded-md border border-border p-0.5">
        {FILTER_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onFilterChange(opt.value)}
            className={cn(
              "rounded-sm px-2.5 py-1 text-xs font-medium transition-colors",
              filter === opt.value
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-muted",
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}
