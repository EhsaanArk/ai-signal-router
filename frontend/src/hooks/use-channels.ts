import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { ChannelInfo } from "@/types/api";

export function useChannels() {
  return useQuery({
    queryKey: ["channels"],
    queryFn: () => apiFetch<ChannelInfo[]>("/channels"),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}
