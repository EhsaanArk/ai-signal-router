import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { useAdminUsers, useAdminUpdateUser } from "@/hooks/use-admin";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "sonner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const PAGE_SIZE = 25;
const TIERS = ["free", "starter", "pro", "elite"];

export function AdminUsersPage() {
  usePageTitle("Admin - Users");
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(0);
  const updateUser = useAdminUpdateUser();

  // Debounce search
  const [timer, setTimer] = useState<ReturnType<typeof setTimeout> | null>(null);
  function handleSearch(value: string) {
    setSearch(value);
    if (timer) clearTimeout(timer);
    const t = setTimeout(() => {
      setDebouncedSearch(value);
      setPage(0);
    }, 300);
    setTimer(t);
  }

  const { data, isLoading } = useAdminUsers(PAGE_SIZE, page * PAGE_SIZE, debouncedSearch || undefined);

  async function handleTierChange(userId: string, tier: string) {
    try {
      await updateUser.mutateAsync({ userId, data: { subscription_tier: tier } });
      toast.success("Tier updated");
    } catch {
      toast.error("Failed to update tier");
    }
  }

  async function handleToggleDisabled(userId: string, disabled: boolean) {
    try {
      await updateUser.mutateAsync({ userId, data: { is_disabled: disabled } });
      toast.success(disabled ? "User disabled" : "User enabled");
    } catch {
      toast.error("Failed to update status");
    }
  }

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">Users ({data?.total ?? "..."})</h2>
      </div>

      {/* Search */}
      <div className="relative max-w-xs">
        <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          placeholder="Search by email..."
          value={search}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleSearch(e.target.value)}
          className="h-8 pl-8 text-sm"
        />
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">Email</TableHead>
              <TableHead className="text-xs">Tier</TableHead>
              <TableHead className="text-xs">Status</TableHead>
              <TableHead className="text-xs text-center">Routes</TableHead>
              <TableHead className="text-xs text-center">Signals</TableHead>
              <TableHead className="text-xs text-center">TG</TableHead>
              <TableHead className="text-xs">Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 7 }).map((_, j) => (
                    <TableCell key={j}><div className="h-4 w-16 bg-muted animate-pulse rounded" /></TableCell>
                  ))}
                </TableRow>
              ))
            ) : data?.items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-xs text-muted-foreground py-8">
                  No users found
                </TableCell>
              </TableRow>
            ) : (
              data?.items.map((user) => (
                <TableRow
                  key={user.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => navigate(`/admin/users/${user.id}`)}
                >
                  <TableCell className="text-xs font-medium">
                    {user.email}
                    {user.is_admin && (
                      <span className="ml-1.5 text-[9px] bg-violet-500/10 text-violet-500 px-1 py-0.5 rounded">
                        admin
                      </span>
                    )}
                  </TableCell>
                  <TableCell onClick={(e: React.MouseEvent) => e.stopPropagation()}>
                    <Select
                      value={user.subscription_tier}
                      onValueChange={(v) => handleTierChange(user.id, v)}
                    >
                      <SelectTrigger className="h-7 w-24 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {TIERS.map((t) => (
                          <SelectItem key={t} value={t} className="text-xs">
                            {t.charAt(0).toUpperCase() + t.slice(1)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell onClick={(e: React.MouseEvent) => e.stopPropagation()}>
                    <Switch
                      checked={!user.is_disabled}
                      onCheckedChange={(v) => handleToggleDisabled(user.id, !v)}
                    />
                  </TableCell>
                  <TableCell className="text-xs text-center font-tabular">{user.rule_count}</TableCell>
                  <TableCell className="text-xs text-center font-tabular">{user.signal_count}</TableCell>
                  <TableCell className="text-center">
                    <span className={`inline-block h-2 w-2 rounded-full ${user.telegram_connected ? "bg-emerald-500" : "bg-zinc-300 dark:bg-zinc-600"}`} />
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(user.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            Page {page + 1} of {totalPages}
          </p>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" className="h-7 text-xs" disabled={page === 0} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <Button variant="outline" size="sm" className="h-7 text-xs" disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
