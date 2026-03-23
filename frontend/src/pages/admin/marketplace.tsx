import { useState } from "react";
import {
  Loader2,
  MoreHorizontal,
  Pencil,
  Plus,
  Radio,
  ShieldOff,
  Store,
  TrendingUp,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Textarea } from "@/components/ui/textarea";
import { usePageTitle } from "@/hooks/use-page-title";
import { cn } from "@/lib/utils";
import {
  useAdminProviders,
  useAdminMarketplaceStats,
  useCreateProvider,
  useUpdateProvider,
  useDeactivateProvider,
} from "@/hooks/use-marketplace-admin";
import type {
  MarketplaceProvider,
  CreateProviderRequest,
  UpdateProviderRequest,
} from "@/hooks/use-marketplace-admin";

const ASSET_CLASSES = ["forex", "crypto", "indices", "commodities"] as const;

// ---------------------------------------------------------------------------
// Stats Cards
// ---------------------------------------------------------------------------

function StatsCards() {
  const { data, isLoading } = useAdminMarketplaceStats();

  const stats = [
    {
      label: "Total Providers",
      value: data?.total_providers,
      icon: Store,
      color: "text-blue-500",
    },
    {
      label: "Active Providers",
      value: data?.active_providers,
      icon: TrendingUp,
      color: "text-emerald-500",
    },
    {
      label: "Total Subscribers",
      value: data?.total_subscribers,
      icon: Users,
      color: "text-violet-500",
    },
    {
      label: "Signals Today",
      value: data?.marketplace_signals_today,
      icon: Radio,
      color: "text-orange-500",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {stats.map((stat) => (
        <Card key={stat.label}>
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-[10px] font-medium text-muted-foreground flex items-center gap-1.5">
              <stat.icon className={cn("h-3 w-3", stat.color)} />
              {stat.label}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            {isLoading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              <p className="text-xl font-bold font-tabular">
                {stat.value ?? "\u2014"}
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add / Edit Provider Sheet
// ---------------------------------------------------------------------------

interface ProviderFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  provider?: MarketplaceProvider | null;
}

function ProviderFormSheet({ open, onOpenChange, provider }: ProviderFormProps) {
  const isEdit = !!provider;
  const createProvider = useCreateProvider();
  const updateProvider = useUpdateProvider();

  const [name, setName] = useState(provider?.name ?? "");
  const [description, setDescription] = useState(provider?.description ?? "");
  const [assetClass, setAssetClass] = useState<string>(
    provider?.asset_class ?? "forex"
  );
  const [channelId, setChannelId] = useState(
    provider?.telegram_channel_id ?? ""
  );

  // Reset form when provider changes
  function resetForm() {
    setName(provider?.name ?? "");
    setDescription(provider?.description ?? "");
    setAssetClass(provider?.asset_class ?? "forex");
    setChannelId(provider?.telegram_channel_id ?? "");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!name.trim() || !channelId.trim()) {
      toast.error("Name and Channel ID are required");
      return;
    }

    try {
      if (isEdit && provider) {
        const data: UpdateProviderRequest = {
          name: name.trim(),
          description: description.trim() || undefined,
          asset_class: assetClass as CreateProviderRequest["asset_class"],
          telegram_channel_id: channelId.trim(),
        };
        await updateProvider.mutateAsync({ id: provider.id, data });
        toast.success("Provider updated");
      } else {
        const data: CreateProviderRequest = {
          name: name.trim(),
          description: description.trim() || undefined,
          asset_class: assetClass as CreateProviderRequest["asset_class"],
          telegram_channel_id: channelId.trim(),
        };
        await createProvider.mutateAsync(data);
        toast.success("Provider created");
      }
      onOpenChange(false);
      resetForm();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to save provider"
      );
    }
  }

  const isPending = createProvider.isPending || updateProvider.isPending;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle className="text-sm">
            {isEdit ? "Edit Provider" : "Add Provider"}
          </SheetTitle>
          <SheetDescription className="text-xs">
            {isEdit
              ? "Update the signal provider details."
              : "Add a new signal provider to the marketplace."}
          </SheetDescription>
        </SheetHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 px-4">
          <div>
            <label className="text-xs font-medium mb-1.5 block">Name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Gold Signals Pro"
              className="text-xs"
            />
          </div>
          <div>
            <label className="text-xs font-medium mb-1.5 block">
              Description
            </label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of the provider..."
              className="text-xs min-h-[80px]"
            />
          </div>
          <div>
            <label className="text-xs font-medium mb-1.5 block">
              Asset Class
            </label>
            <Select value={assetClass} onValueChange={setAssetClass}>
              <SelectTrigger className="text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ASSET_CLASSES.map((ac) => (
                  <SelectItem key={ac} value={ac} className="text-xs capitalize">
                    {ac}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs font-medium mb-1.5 block">
              Telegram Channel ID
            </label>
            <Input
              value={channelId}
              onChange={(e) => setChannelId(e.target.value)}
              placeholder="e.g. -1001234567890"
              className="text-xs font-mono"
            />
          </div>
          <Button type="submit" disabled={isPending} className="mt-2">
            {isPending ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : null}
            {isEdit ? "Update Provider" : "Create Provider"}
          </Button>
        </form>
      </SheetContent>
    </Sheet>
  );
}

// ---------------------------------------------------------------------------
// Provider Table
// ---------------------------------------------------------------------------

function ProviderTable() {
  const { data: providers, isLoading } = useAdminProviders();
  const deactivateProvider = useDeactivateProvider();
  const [editProvider, setEditProvider] = useState<MarketplaceProvider | null>(
    null
  );
  const [deactivateId, setDeactivateId] = useState<string | null>(null);

  async function handleDeactivate() {
    if (!deactivateId) return;
    try {
      await deactivateProvider.mutateAsync(deactivateId);
      toast.success("Provider deactivated");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to deactivate provider"
      );
    } finally {
      setDeactivateId(null);
    }
  }



  if (isLoading) {
    return (
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">Name</TableHead>
              <TableHead className="text-xs">Asset Class</TableHead>
              <TableHead className="text-xs">Channel ID</TableHead>
              <TableHead className="text-xs">Status</TableHead>
              <TableHead className="text-xs text-center">Subscribers</TableHead>
              <TableHead className="text-xs text-center">Win Rate</TableHead>
              <TableHead className="text-xs w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {Array.from({ length: 4 }).map((_, i) => (
              <TableRow key={i}>
                {Array.from({ length: 7 }).map((_, j) => (
                  <TableCell key={j}>
                    <Skeleton className="h-4 w-16" />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    );
  }

  if (!providers?.length) {
    return (
      <div className="rounded-md border py-12 text-center">
        <p className="text-xs text-muted-foreground">
          No providers yet. Click "Add Provider" to get started.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">Name</TableHead>
              <TableHead className="text-xs">Asset Class</TableHead>
              <TableHead className="text-xs">Channel ID</TableHead>
              <TableHead className="text-xs">Status</TableHead>
              <TableHead className="text-xs text-center">Subscribers</TableHead>
              <TableHead className="text-xs text-center">Win Rate</TableHead>
              <TableHead className="text-xs w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {providers.map((provider) => (
              <TableRow key={provider.id} className="hover:bg-muted/40">
                <TableCell className="py-2">
                  <div>
                    <p className="text-xs font-medium">{provider.name}</p>
                    {provider.description && (
                      <p className="text-[10px] text-muted-foreground truncate max-w-[200px]">
                        {provider.description}
                      </p>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-xs capitalize">
                  {provider.asset_class}
                </TableCell>
                <TableCell className="text-xs font-mono text-muted-foreground">
                  {provider.telegram_channel_id}
                </TableCell>
                <TableCell>
                  <Badge
                    variant="outline"
                    className={cn(
                      "text-[10px] capitalize",
                      provider.is_active
                        ? "bg-emerald-500/10 text-emerald-600"
                        : "bg-zinc-500/10 text-zinc-500"
                    )}
                  >
                    {provider.is_active ? "Active" : "Inactive"}
                  </Badge>
                </TableCell>
                <TableCell className="text-xs text-center font-tabular">
                  {provider.subscriber_count}
                </TableCell>
                <TableCell className="text-xs text-center font-tabular">
                  {provider.win_rate != null
                    ? `${provider.win_rate}%`
                    : "\u2014"}
                </TableCell>
                <TableCell className="py-2">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-7 w-7">
                        <MoreHorizontal className="h-3.5 w-3.5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => setEditProvider(provider)}
                      >
                        <Pencil className="mr-2 h-3.5 w-3.5" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => setDeactivateId(provider.id)}
                      >
                        <ShieldOff className="mr-2 h-3.5 w-3.5" />
                        Deactivate
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Edit Sheet */}
      <ProviderFormSheet
        open={!!editProvider}
        onOpenChange={(open) => !open && setEditProvider(null)}
        provider={editProvider}
      />

      {/* Deactivate Confirmation */}
      <AlertDialog
        open={!!deactivateId}
        onOpenChange={(open: boolean) => !open && setDeactivateId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate provider?</AlertDialogTitle>
            <AlertDialogDescription>
              This will hide the provider from the marketplace and stop routing
              signals to subscribers. Existing subscriptions will be paused.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeactivate}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Deactivate
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function AdminMarketplacePage() {
  usePageTitle("Admin - Marketplace");
  const [showAdd, setShowAdd] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">Marketplace</h2>
        <Button
          size="sm"
          className="h-7 text-xs"
          onClick={() => setShowAdd(true)}
        >
          <Plus className="mr-1 h-3 w-3" />
          Add Provider
        </Button>
      </div>

      <StatsCards />
      <ProviderTable />

      {/* Add Provider Sheet */}
      <ProviderFormSheet
        open={showAdd}
        onOpenChange={setShowAdd}
        provider={null}
      />
    </div>
  );
}

export default AdminMarketplacePage;
