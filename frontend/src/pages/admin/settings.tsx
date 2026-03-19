import { useState } from "react";
import { Clock, Loader2, Save } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminSettings, useUpdateAdminSettings } from "@/hooks/use-admin";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "sonner";

const SETTING_META: Record<string, { label: string; icon: typeof Clock; unit: string; min: number; max: number; help: string }> = {
  backfill_max_age_seconds: {
    label: "Signal Freshness Threshold",
    icon: Clock,
    unit: "seconds",
    min: 10,
    max: 600,
    help: "When the listener reconnects after a restart, signals older than this are ignored. Lower = safer (fewer stale trades), higher = fewer missed signals.",
  },
};

export function AdminSettingsPage() {
  usePageTitle("Global Settings");
  const { data: settings, isLoading } = useAdminSettings();
  const updateSettings = useUpdateAdminSettings();
  const [edits, setEdits] = useState<Record<string, string>>({});

  const hasChanges = Object.keys(edits).length > 0;

  function handleSave() {
    // Validate before sending
    for (const [key, value] of Object.entries(edits)) {
      const meta = SETTING_META[key];
      if (!meta) continue;
      const num = Number(value);
      if (isNaN(num) || num < meta.min || num > meta.max) {
        toast.error(`${meta.label} must be between ${meta.min} and ${meta.max}`);
        return;
      }
    }

    updateSettings.mutate(edits, {
      onSuccess: () => {
        setEdits({});
        toast.success("Settings saved");
      },
      onError: (err) => {
        toast.error(err instanceof Error ? err.message : "Failed to save settings");
      },
    });
  }

  if (isLoading) {
    return (
      <div className="space-y-4 max-w-xl">
        <h2 className="text-sm font-medium">Global Settings</h2>
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-xl">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">Global Settings</h2>
        {hasChanges && (
          <Button
            size="sm"
            onClick={handleSave}
            disabled={updateSettings.isPending}
          >
            {updateSettings.isPending ? (
              <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
            ) : (
              <Save className="mr-1.5 h-3 w-3" />
            )}
            Save Changes
          </Button>
        )}
      </div>

      <Card>
        <CardHeader className="pb-3 pt-4 px-4">
          <CardTitle className="text-xs font-medium">Signal Processing</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 space-y-4">
          {(settings ?? []).map((setting) => {
            const meta = SETTING_META[setting.key];
            if (!meta) return null;
            const currentValue = edits[setting.key] ?? setting.value;
            const Icon = meta.icon;

            return (
              <div key={setting.key} className="space-y-1.5">
                <Label htmlFor={setting.key} className="text-xs flex items-center gap-1.5">
                  <Icon className="h-3 w-3 text-muted-foreground" />
                  {meta.label}
                </Label>
                <div className="flex items-center gap-2">
                  <Input
                    id={setting.key}
                    type="number"
                    min={meta.min}
                    max={meta.max}
                    value={currentValue}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                      setEdits((prev) => ({ ...prev, [setting.key]: e.target.value }));
                    }}
                    className="h-8 text-sm w-24 font-mono"
                  />
                  <span className="text-xs text-muted-foreground">{meta.unit}</span>
                </div>
                <p className="text-[10px] text-muted-foreground">{meta.help}</p>
                {setting.updated_by && (
                  <p className="text-[10px] text-muted-foreground/60">
                    Last updated by {setting.updated_by}
                    {setting.updated_at && ` on ${new Date(setting.updated_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`}
                  </p>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}

export default AdminSettingsPage;
