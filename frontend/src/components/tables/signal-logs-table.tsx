import { Fragment, useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/shared/status-badge";
import { LogDetailRow } from "./log-detail-row";
import { formatRelativeTime, truncateText } from "@/lib/utils";
import type { SignalLogResponse } from "@/types/api";

interface Props {
  logs: SignalLogResponse[];
}

export function SignalLogsTable({ logs }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Time</TableHead>
            <TableHead>Signal</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {logs.map((log) => (
            <Fragment key={log.id}>
              <TableRow
                className="cursor-pointer hover:bg-muted/50"
                onClick={() =>
                  setExpandedId(expandedId === log.id ? null : log.id)
                }
              >
                <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                  {formatRelativeTime(log.processed_at)}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {truncateText(log.raw_message, 80)}
                </TableCell>
                <TableCell>
                  <StatusBadge
                    status={log.status as "success" | "failed" | "ignored"}
                  />
                </TableCell>
              </TableRow>
              {expandedId === log.id && <LogDetailRow log={log} />}
            </Fragment>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
