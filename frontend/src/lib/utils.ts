import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export function humanizeAction(action: string): string {
  return action
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export const DESTINATION_TYPE_LABELS: Record<string, string> = {
  sagemaster_forex: "Forex",
  sagemaster_crypto: "Crypto",
  custom: "Custom",
};

export const DESTINATION_TYPE_LABELS_FULL: Record<string, string> = {
  sagemaster_forex: "SageMaster Forex",
  sagemaster_crypto: "SageMaster Crypto",
  custom: "Custom Webhook",
};

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

const UUID_RE = /([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\/?$/i;

export function extractAccountIdFromUrl(url: string): string | null {
  const m = url.match(UUID_RE);
  return m ? m[1] : null;
}

export function extractTemplateMetadata(json: string): {
  assistId: string | null;
  exchange: string | null;
} {
  try {
    const obj = JSON.parse(json);
    if (typeof obj !== "object" || obj === null) return { assistId: null, exchange: null };
    const assistId = obj.aiAssistId ?? obj.assistId ?? null;
    const exchange = obj.exchange ?? obj.source ?? null;
    return { assistId, exchange };
  } catch {
    return { assistId: null, exchange: null };
  }
}
