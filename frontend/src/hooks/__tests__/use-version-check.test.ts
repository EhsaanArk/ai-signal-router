import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

// Mock react-router-dom
let mockPathname = "/dashboard";
vi.mock("react-router-dom", () => ({
  useLocation: () => ({ pathname: mockPathname }),
  MemoryRouter: ({ children }: { children: ReactNode }) => children,
}));

// Mock Sentry
vi.mock("@sentry/react", () => ({
  addBreadcrumb: vi.fn(),
}));

import { useVersionCheck } from "@/hooks/use-version-check";

beforeEach(() => {
  mockPathname = "/dashboard";
  window.__BUILD_TIME__ = 1000;
});

afterEach(() => {
  vi.restoreAllMocks();
  delete window.__BUILD_TIME__;
});

describe("useVersionCheck", () => {
  it("returns stale=false when versions match", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ buildTime: 1000 }),
      }),
    );

    const { result } = renderHook(() => useVersionCheck());

    await waitFor(() => {
      expect(fetch).toHaveBeenCalled();
    });

    expect(result.current.stale).toBe(false);
  });

  it("returns stale=true when versions differ", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ buildTime: 2000 }),
      }),
    );

    const { result } = renderHook(() => useVersionCheck());

    await waitFor(() => {
      expect(result.current.stale).toBe(true);
    });
  });

  it("silently handles fetch errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("network error")),
    );

    const { result } = renderHook(() => useVersionCheck());

    await waitFor(() => {
      expect(fetch).toHaveBeenCalled();
    });

    expect(result.current.stale).toBe(false);
  });

  it("throttles checks (< 30s between calls)", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ buildTime: 1000 }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = renderHook(() => useVersionCheck());

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    // Simulate a navigation (pathname change triggers useEffect)
    mockPathname = "/settings";
    rerender();

    // Should not call fetch again — throttled (Date.now() hasn't advanced 30s)
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
