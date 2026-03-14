import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, MessageSquare, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useChannels } from "@/hooks/use-channels";
import { cn } from "@/lib/utils";

interface Props {
  initialData?: { source_channel_id?: string; rule_name?: string };
  onNext: (channelId: string, channelName: string, ruleName: string) => void;
}

export function StepSelectChannel({ initialData, onNext }: Props) {
  const { data: channels, isLoading, error } = useChannels();
  const [selected, setSelected] = useState(initialData?.source_channel_id ?? "");
  const [search, setSearch] = useState("");
  const [ruleName, setRuleName] = useState(initialData?.rule_name ?? "");

  if (isLoading) {
    return (
      <div className="space-y-1">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-3 text-center py-6">
        <MessageSquare className="mx-auto h-6 w-6 text-muted-foreground" />
        <p className="text-xs text-muted-foreground">
          Connect Telegram first to see your channels.
        </p>
        <Button asChild variant="outline" size="sm">
          <Link to="/telegram">Connect Telegram</Link>
        </Button>
      </div>
    );
  }

  if (!channels?.length) {
    return (
      <p className="text-xs text-muted-foreground py-6 text-center">
        No channels found. Make sure you're subscribed to signal channels in Telegram.
      </p>
    );
  }

  const filtered = channels.filter((ch) =>
    ch.title.toLowerCase().includes(search.toLowerCase()) ||
    (ch.username && ch.username.toLowerCase().includes(search.toLowerCase()))
  );

  const selectedChannel = channels.find((c) => c.id === selected);
  const isFiltering = search.trim().length > 0;

  return (
    <div className="space-y-3">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)}
          placeholder="Search channels..."
          className="h-8 pl-8 text-sm"
        />
      </div>

      {/* Count */}
      <p className="text-[10px] text-muted-foreground">
        {isFiltering
          ? `${filtered.length} of ${channels.length} channels`
          : `${channels.length} channels`
        }
      </p>

      {/* Scrollable list */}
      <div className="rounded-md border max-h-[300px] overflow-y-auto">
        {filtered.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-6">
            No channels match &ldquo;{search}&rdquo;
          </p>
        ) : (
          filtered.map((ch) => {
            const isSelected = selected === ch.id;
            return (
              <button
                key={ch.id}
                type="button"
                onClick={() => setSelected(ch.id)}
                className={cn(
                  "flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors border-l-2",
                  "hover:bg-muted/50",
                  isSelected
                    ? "bg-primary/5 border-l-primary"
                    : "border-l-transparent"
                )}
              >
                <div className="flex-1 min-w-0">
                  <p className={cn("text-xs truncate", isSelected && "font-medium")}>
                    {ch.title}
                  </p>
                  {ch.username && (
                    <p className="text-[10px] text-muted-foreground truncate">
                      @{ch.username}
                    </p>
                  )}
                </div>
                {isSelected && (
                  <Check className="h-3.5 w-3.5 text-primary shrink-0" />
                )}
              </button>
            );
          })
        )}
      </div>

      {/* Rule Name */}
      {selected && (
        <div className="space-y-1.5">
          <Label htmlFor="rule-name" className="text-xs">Route Name (optional)</Label>
          <Input
            id="rule-name"
            value={ruleName}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRuleName(e.target.value)}
            placeholder="e.g., Gold Aggressive, EURUSD Demo"
            className="h-8 text-sm"
          />
          <p className="text-[10px] text-muted-foreground">
            Give this route a name to identify it later
          </p>
        </div>
      )}

      {/* Selected indicator + Next */}
      <div className="flex items-center justify-between pt-1">
        {selectedChannel ? (
          <p className="text-[11px] text-muted-foreground truncate max-w-[200px]">
            Selected: <span className="font-medium text-foreground">{selectedChannel.title}</span>
          </p>
        ) : (
          <p className="text-[11px] text-muted-foreground">Select a channel to continue</p>
        )}
        <Button
          size="sm"
          className="h-7 text-xs"
          onClick={() => onNext(selected, selectedChannel?.title || selected, ruleName)}
          disabled={!selected}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
