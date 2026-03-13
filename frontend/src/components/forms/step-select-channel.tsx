import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useChannels } from "@/hooks/use-channels";
import { MessageSquare } from "lucide-react";

interface Props {
  onNext: (channelId: string, channelName: string) => void;
}

export function StepSelectChannel({ onNext }: Props) {
  const { data: channels, isLoading, error } = useChannels();
  const [selected, setSelected] = useState("");

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4 text-center">
        <MessageSquare className="mx-auto h-8 w-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          Connect Telegram first to see your channels.
        </p>
        <Button asChild variant="outline">
          <Link to="/telegram">Connect Telegram</Link>
        </Button>
      </div>
    );
  }

  if (!channels?.length) {
    return (
      <p className="text-sm text-muted-foreground">
        No channels found. Make sure you're subscribed to signal channels in
        Telegram.
      </p>
    );
  }

  const selectedChannel = channels.find((c) => c.id === selected);

  return (
    <div className="space-y-4">
      <RadioGroup value={selected} onValueChange={setSelected}>
        {channels.map((ch) => (
          <div
            key={ch.id}
            className="flex items-center space-x-3 rounded-md border p-3"
          >
            <RadioGroupItem value={ch.id} id={ch.id} />
            <Label htmlFor={ch.id} className="flex-1 cursor-pointer">
              <span className="font-medium">{ch.title}</span>
              {ch.username && (
                <span className="ml-2 text-xs text-muted-foreground">
                  @{ch.username}
                </span>
              )}
            </Label>
          </div>
        ))}
      </RadioGroup>
      <Button
        onClick={() =>
          onNext(selected, selectedChannel?.title || selected)
        }
        disabled={!selected}
      >
        Next
      </Button>
    </div>
  );
}
