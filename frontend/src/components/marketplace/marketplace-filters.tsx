import { cn } from "@/lib/utils";
import type { MarketplaceSort, MarketplaceFilter } from "@/types/marketplace";

const FILTERS: { value: MarketplaceFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "forex", label: "Forex" },
  { value: "crypto", label: "Crypto" },
];

const SORTS: { value: MarketplaceSort; label: string }[] = [
  { value: "subscribers", label: "Followers" },
  { value: "signals", label: "Signals" },
  { value: "win_rate", label: "Reliability" },
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
            aria-pressed={filter === f.value}
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

      {/* Sort — segmented control (matching filter style) */}
      <div className="flex items-center gap-1.5 text-[11px]">
        <span className="text-muted-foreground">Sort:</span>
        <div className="flex items-center gap-0.5 rounded-md bg-muted/40 p-0.5">
          {SORTS.map((s) => (
            <button
              key={s.value}
              type="button"
              aria-pressed={sort === s.value}
              onClick={() => onSortChange(s.value)}
              className={cn(
                "px-2.5 py-1 text-[11px] font-medium rounded-[5px] transition-colors",
                sort === s.value
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
