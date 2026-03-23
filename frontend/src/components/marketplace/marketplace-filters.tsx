import { cn } from "@/lib/utils";
import type { MarketplaceSort, MarketplaceFilter } from "@/types/marketplace";

const FILTERS: { value: MarketplaceFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "forex", label: "Forex" },
  { value: "crypto", label: "Crypto" },
];

const SORTS: { value: MarketplaceSort; label: string }[] = [
  { value: "win_rate", label: "Win Rate" },
  { value: "pnl", label: "P&L" },
  { value: "signals", label: "Signals" },
  { value: "subscribers", label: "Followers" },
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
    <div className="flex items-center gap-4 flex-wrap">
      {/* Asset filter — segmented control */}
      <div className="flex items-center gap-0.5 rounded-md bg-muted/40 p-0.5">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => onFilterChange(f.value)}
            className={cn(
              "px-3 py-1 text-[11px] font-medium rounded-[5px] transition-colors",
              filter === f.value
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Sort — inline text tabs */}
      <div className="flex items-center gap-1 text-[11px]">
        <span className="text-muted-foreground mr-1">Sort:</span>
        {SORTS.map((s) => (
          <button
            key={s.value}
            type="button"
            onClick={() => onSortChange(s.value)}
            className={cn(
              "px-2 py-0.5 rounded transition-colors",
              sort === s.value
                ? "text-foreground font-medium"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
