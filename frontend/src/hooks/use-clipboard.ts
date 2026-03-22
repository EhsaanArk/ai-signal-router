import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";

/**
 * Copy text to clipboard with optional toast feedback.
 *
 * Returns `[copy, copied]`:
 * - `copy(text, label?)` — copies text and shows a toast (default label "Copied")
 * - `copied` — true for 1.5 s after a successful copy
 */
export function useCopyToClipboard(): [
  copy: (text: string, label?: string) => void,
  copied: boolean,
] {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const copy = useCallback((text: string, label = "Copied") => {
    navigator.clipboard.writeText(text).then(() => {
      toast.success(label);
      setCopied(true);
      clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 1500);
    });
  }, []);

  return [copy, copied];
}
