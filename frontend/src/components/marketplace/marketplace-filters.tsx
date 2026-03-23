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
    <div className="flex items-center gap-4">
      {/* Filter pills — refined with left-border accent pattern */}
      <div className="flex items-center gap-0.5">
        {FILTER_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onFilterChange(opt.value)}
            className={cn(
              "relative rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              filter === opt.value
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
            )}
          >
            {filter === opt.value && (
              <span className="absolute left-0 top-1 bottom-1 w-0.5 rounded-r-full bg-primary" />
            )}
            {opt.label}
          </button>
        ))}
      </div>

      <span className="h-4 w-px bg-border/60" />

      {/* Sort dropdown — compact */}
      <Select value={sort} onValueChange={(v) => onSortChange(v as MarketplaceSort)}>
        <SelectTrigger className="h-7 w-[120px] text-[11px] border-border/60">
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
    </div>
  );
}
