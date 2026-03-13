import { toast } from "sonner";

export function useCopyToClipboard() {
  return (text: string, label = "Copied") => {
    navigator.clipboard.writeText(text).then(() => toast.success(label));
  };
}
