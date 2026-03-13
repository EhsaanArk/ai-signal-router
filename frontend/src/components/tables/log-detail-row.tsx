import { Copy } from "lucide-react";
import { TableCell, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { useCopyToClipboard } from "@/hooks/use-clipboard";
import type { SignalLogResponse } from "@/types/api";

interface Props {
  log: SignalLogResponse;
}

export function LogDetailRow({ log }: Props) {
  const copy = useCopyToClipboard();

  return (
    <TableRow>
      <TableCell colSpan={3} className="bg-muted/50 p-4">
        <div className="space-y-3 text-sm">
          <div>
            <div className="flex items-center justify-between mb-1">
              <p className="font-medium text-xs text-muted-foreground">
                Raw Message
              </p>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs"
                onClick={() => copy(log.raw_message, "Raw message copied")}
              >
                <Copy className="mr-1 h-3 w-3" />
                Copy
              </Button>
            </div>
            <pre className="whitespace-pre-wrap rounded bg-muted p-2 font-mono text-xs max-h-60 overflow-y-auto">
              {log.raw_message}
            </pre>
          </div>

          {log.parsed_data && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="font-medium text-xs text-muted-foreground">
                  Parsed Data
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs"
                  onClick={() =>
                    copy(
                      JSON.stringify(log.parsed_data, null, 2),
                      "Parsed data copied"
                    )
                  }
                >
                  <Copy className="mr-1 h-3 w-3" />
                  Copy
                </Button>
              </div>
              <pre className="whitespace-pre-wrap rounded bg-muted p-2 font-mono text-xs max-h-60 overflow-y-auto">
                {JSON.stringify(log.parsed_data, null, 2)}
              </pre>
            </div>
          )}

          {log.webhook_payload && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="font-medium text-xs text-muted-foreground">
                  Webhook Payload
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs"
                  onClick={() =>
                    copy(
                      JSON.stringify(log.webhook_payload, null, 2),
                      "Webhook payload copied"
                    )
                  }
                >
                  <Copy className="mr-1 h-3 w-3" />
                  Copy
                </Button>
              </div>
              <pre className="whitespace-pre-wrap rounded bg-muted p-2 font-mono text-xs max-h-60 overflow-y-auto">
                {JSON.stringify(log.webhook_payload, null, 2)}
              </pre>
            </div>
          )}

          {log.error_message && (
            <div>
              <p className="font-medium text-xs text-muted-foreground mb-1">
                Error
              </p>
              <p className="text-destructive text-xs">{log.error_message}</p>
            </div>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}
