import { useEffect } from "react";

const BASE = "Sage Radar AI";

export function usePageTitle(title?: string) {
  useEffect(() => {
    document.title = title ? `${title} | ${BASE}` : BASE;
    return () => {
      document.title = BASE;
    };
  }, [title]);
}
