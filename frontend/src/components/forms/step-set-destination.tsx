import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

interface Props {
  onNext: (url: string, version: "V1" | "V2") => void;
  onBack: () => void;
}

export function StepSetDestination({ onNext, onBack }: Props) {
  const [url, setUrl] = useState("");
  const [version, setVersion] = useState<"V1" | "V2">("V1");
  const [urlError, setUrlError] = useState("");

  function handleNext() {
    try {
      new URL(url);
    } catch {
      setUrlError("Enter a valid URL (e.g., https://...)");
      return;
    }
    setUrlError("");
    onNext(url, version);
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="webhook-url">Webhook URL</Label>
        <Input
          id="webhook-url"
          type="url"
          placeholder="https://your-webhook-url.com/..."
          value={url}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            setUrl(e.target.value);
            if (urlError) setUrlError("");
          }}
        />
        {urlError && (
          <p className="text-xs text-destructive">{urlError}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label>Payload Version</Label>
        <RadioGroup
          value={version}
          onValueChange={(v: string) => setVersion(v as "V1" | "V2")}
        >
          <div className="flex items-center space-x-3 rounded-md border p-3">
            <RadioGroupItem value="V1" id="v1" />
            <Label htmlFor="v1" className="cursor-pointer">
              <span className="font-medium">V1</span>
              <span className="ml-2 text-xs text-muted-foreground">
                Static strategy trigger
              </span>
            </Label>
          </div>
          <div className="flex items-center space-x-3 rounded-md border p-3">
            <RadioGroupItem value="V2" id="v2" />
            <Label htmlFor="v2" className="cursor-pointer">
              <span className="font-medium">V2</span>
              <span className="ml-2 text-xs text-muted-foreground">
                Full signal with TP/SL
              </span>
            </Label>
          </div>
        </RadioGroup>
      </div>

      <div className="flex gap-2">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button onClick={handleNext} disabled={!url}>
          Next
        </Button>
      </div>
    </div>
  );
}
