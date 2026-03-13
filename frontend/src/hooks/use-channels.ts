import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { ChannelInfo } from "@/types/api";

export function useChannels() {
  return useQuery({
    queryKey: ["channels"],
    queryFn: () => apiFetch<ChannelInfo[]>("/channels"),
    retry: false,
  });
}
