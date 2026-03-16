import { useState, useMemo } from "react";
import {
  Bell,
  BookOpen,
  Filter,
  Layers,
  Search,
  Send,
  Shield,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { usePageTitle } from "@/hooks/use-page-title";
import {
  SYSTEM_RULES,
  type RuleValue,
  type SystemRule,
  type SystemRuleCategory,
} from "@/lib/system-rules";

const ICON_MAP: Record<string, LucideIcon> = {
  Layers,
  Zap,
  Filter,
  Send,
  Bell,
  Shield,
};

function isTable(v: RuleValue): v is { headers: string[]; rows: string[][] } {
  return typeof v === "object" && !Array.isArray(v) && "headers" in v;
}

function isRecord(v: RuleValue): v is Record<string, string | string[]> {
  return typeof v === "object" && !Array.isArray(v) && !("headers" in v);
}

function RuleValueDisplay({ value }: { value: RuleValue }) {
  if (typeof value === "string") {
    return <p className="text-muted-foreground text-xs">{value}</p>;
  }

  if (Array.isArray(value)) {
    return (
      <ul className="space-y-1 text-xs text-muted-foreground list-none">
        {value.map((item, i) => (
          <li key={i} className="flex items-start gap-2">
            <span className="text-muted-foreground/50 shrink-0">-</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    );
  }

  if (isTable(value)) {
    return (
      <div className="rounded-md border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              {value.headers.map((h) => (
                <TableHead key={h} className="text-xs h-8">
                  {h}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {value.rows.map((row, i) => (
              <TableRow key={i}>
                {row.map((cell, j) => (
                  <TableCell key={j} className="text-xs py-1.5">
                    {cell}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    );
  }

  if (isRecord(value)) {
    const entries = Object.entries(value);
    return (
      <div className="rounded-md border overflow-hidden">
        <Table>
          <TableBody>
            {entries.map(([k, v]) => (
              <TableRow key={k}>
                <TableCell className="text-xs py-1.5 font-medium w-1/3">
                  {k}
                </TableCell>
                <TableCell className="text-xs py-1.5 text-muted-foreground">
                  {Array.isArray(v) ? v.join(", ") : v}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    );
  }

  return null;
}

function RuleCard({ rule }: { rule: SystemRule }) {
  return (
    <div className="space-y-1.5 py-3 first:pt-0 last:pb-0">
      <h4 className="text-xs font-medium">{rule.label}</h4>
      <p className="text-xs text-muted-foreground/70">{rule.description}</p>
      <div className="pt-1">
        <RuleValueDisplay value={rule.value} />
      </div>
    </div>
  );
}

function filterCategory(
  category: SystemRuleCategory,
  query: string
): SystemRuleCategory | null {
  const q = query.toLowerCase();

  // Match on category label/description
  if (
    category.label.toLowerCase().includes(q) ||
    category.description.toLowerCase().includes(q)
  ) {
    return category;
  }

  // Match on individual rules
  const matchedRules = category.rules.filter(
    (rule) =>
      rule.label.toLowerCase().includes(q) ||
      rule.description.toLowerCase().includes(q) ||
      JSON.stringify(rule.value).toLowerCase().includes(q)
  );

  if (matchedRules.length === 0) return null;
  return { ...category, rules: matchedRules };
}

export function AdminSystemRulesPage() {
  usePageTitle("System Rules");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!search.trim()) return SYSTEM_RULES;
    return SYSTEM_RULES.map((cat) => filterCategory(cat, search.trim())).filter(
      Boolean
    ) as SystemRuleCategory[];
  }, [search]);

  const allKeys = filtered.map((c) => c.category);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-muted-foreground" />
            System Rules
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Read-only reference of all hardcoded business rules governing signal
            processing, dispatch, and security.
          </p>
        </div>
      </div>

      <div className="relative max-w-xs">
        <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          placeholder="Search rules..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-8 h-8 text-xs"
        />
      </div>

      {filtered.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            No rules match "{search}"
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Accordion type="multiple" defaultValue={allKeys}>
              {filtered.map((category) => {
                const Icon = ICON_MAP[category.icon] ?? Layers;
                return (
                  <AccordionItem
                    key={category.category}
                    value={category.category}
                  >
                    <AccordionTrigger className="px-4 hover:no-underline">
                      <div className="flex items-center gap-2">
                        <Icon className="h-4 w-4 text-muted-foreground" />
                        <span>{category.label}</span>
                        <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                          {category.rules.length}
                        </Badge>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="px-4">
                      <p className="text-xs text-muted-foreground/70 mb-3">
                        {category.description}
                      </p>
                      <div className="divide-y">
                        {category.rules.map((rule) => (
                          <RuleCard key={rule.key} rule={rule} />
                        ))}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
            </Accordion>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default AdminSystemRulesPage;
