import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  isChunkLoadError,
  getChunkReloadKey,
} from "@/lib/lazy-retry";

// ---------- helpers ----------
function mockSessionStorage() {
  const store = new Map<string, string>();
  return {
    getItem: vi.fn((k: string) => store.get(k) ?? null),
    setItem: vi.fn((k: string, v: string) => store.set(k, v)),
    removeItem: vi.fn((k: string) => store.delete(k)),
    clear: vi.fn(() => store.clear()),
    get length() {
      return store.size;
    },
    key: vi.fn(() => null),
  } satisfies Storage;
}

// ---------- setup ----------
let storage: ReturnType<typeof mockSessionStorage>;

beforeEach(() => {
  storage = mockSessionStorage();
  vi.stubGlobal("sessionStorage", storage);
  vi.stubGlobal("location", {
    ...window.location,
    pathname: "/dashboard",
    reload: vi.fn(),
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------- getChunkReloadKey ----------
describe("getChunkReloadKey", () => {
  it("returns key with current pathname when no arg supplied", () => {
    expect(getChunkReloadKey()).toBe("chunk-reload-/dashboard");
  });

  it("returns key with supplied pathname", () => {
    expect(getChunkReloadKey("/settings")).toBe("chunk-reload-/settings");
  });
});

// ---------- isChunkLoadError ----------
describe("isChunkLoadError", () => {
  it('detects "dynamically imported module" error (Chrome/Firefox)', () => {
    const err = new Error(
      "Failed to fetch dynamically imported module: https://example.com/chunk.js",
    );
    expect(isChunkLoadError(err)).toBe(true);
  });

  it('detects "importing a module script" error (Safari)', () => {
    const err = new Error("Importing a module script failed.");
    expect(isChunkLoadError(err)).toBe(true);
  });

  it('detects "loading chunk" error', () => {
    const err = new Error("Loading chunk 42 failed.");
    expect(isChunkLoadError(err)).toBe(true);
  });

  it('detects "loading css chunk" error', () => {
    const err = new Error("Loading CSS chunk styles-abc123 failed.");
    expect(isChunkLoadError(err)).toBe(true);
  });

  it("returns false for a generic Error", () => {
    expect(isChunkLoadError(new Error("something broke"))).toBe(false);
  });

  it("returns false for non-Error values", () => {
    expect(isChunkLoadError("string")).toBe(false);
    expect(isChunkLoadError(42)).toBe(false);
    expect(isChunkLoadError(null)).toBe(false);
    expect(isChunkLoadError(undefined)).toBe(false);
  });

  it('returns false for "Failed to fetch" without module context (API errors)', () => {
    const err = new TypeError("Failed to fetch");
    expect(isChunkLoadError(err)).toBe(false);
  });
});

// ---------- lazyRetry ----------
// We test lazyRetry by triggering React.lazy's init function via its internal
// _payload._result. React.lazy is deferred — it doesn't call importFn until
// the component is actually rendered (or the init is invoked).
describe("lazyRetry retry behaviour", () => {
  it("returns a lazy component that calls importFn when initialized", async () => {
    const fakeModule = { default: () => null };
    const importFn = vi.fn().mockResolvedValue(fakeModule);
    const { lazyRetry } = await import("@/lib/lazy-retry");

    const LazyComponent = lazyRetry(importFn);
    expect(LazyComponent).toBeDefined();

    // React.lazy is deferred — trigger the init
    const payload = (LazyComponent as unknown as { _payload: { _result: () => Promise<unknown> } })._payload;
    const result = await payload._result();
    expect(result).toBe(fakeModule);
    expect(importFn).toHaveBeenCalledTimes(1);
  });

  it("retries on failure and succeeds — clears reload flag", async () => {
    vi.useFakeTimers();
    try {
      const fakeModule = { default: () => null };
      const importFn = vi
        .fn()
        .mockRejectedValueOnce(new Error("network blip"))
        .mockResolvedValueOnce(fakeModule);

      const { lazyRetry } = await import("@/lib/lazy-retry");
      const LazyComponent = lazyRetry(importFn);

      const payload = (LazyComponent as unknown as { _payload: { _result: () => Promise<unknown> } })._payload;
      const promise = payload._result();

      await vi.advanceTimersByTimeAsync(600);

      const result = await promise;
      expect(result).toBe(fakeModule);
      expect(importFn).toHaveBeenCalledTimes(2);
      expect(storage.removeItem).toHaveBeenCalledWith("chunk-reload-/dashboard");
    } finally {
      vi.useRealTimers();
    }
  });

  it("reloads page when both attempts fail and no previous reload", async () => {
    vi.useFakeTimers();
    try {
      const importFn = vi.fn().mockRejectedValue(new Error("chunk gone"));

      const { lazyRetry } = await import("@/lib/lazy-retry");
      const LazyComponent = lazyRetry(importFn);

      const payload = (LazyComponent as unknown as { _payload: { _result: () => Promise<unknown> } })._payload;
      // The never-resolving promise means we can't await it.
      // Start it and suppress the unhandled rejection.
      payload._result().catch(() => { /* expected — never-resolving promise path */ });

      await vi.advanceTimersByTimeAsync(600);
      // Flush microtasks
      await vi.advanceTimersByTimeAsync(0);

      expect(storage.setItem).toHaveBeenCalledWith("chunk-reload-/dashboard", "1");
      expect(window.location.reload).toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("throws when both attempts fail and already reloaded", async () => {
    vi.useFakeTimers();
    // Suppress the unhandled rejection that React.lazy's internal promise chain creates.
    // React.lazy wraps our factory in its own .then() which produces a secondary rejected
    // promise we can't directly catch from test code.
    const suppressHandler = (reason: unknown) => {
      if (reason instanceof Error && reason.message === "Failed to load page after retry and reload") {
        // expected — swallow it
        return;
      }
    };
    process.on("unhandledRejection", suppressHandler);
    try {
      storage.setItem("chunk-reload-/dashboard", "1");
      const importFn = vi.fn().mockRejectedValue(new Error("chunk gone"));

      const { lazyRetry } = await import("@/lib/lazy-retry");
      const LazyComponent = lazyRetry(importFn);

      const payload = (LazyComponent as unknown as { _payload: { _result: () => Promise<unknown> } })._payload;
      const promise = payload._result();

      await vi.advanceTimersByTimeAsync(600);

      await expect(promise).rejects.toThrow("Failed to load page after retry and reload");
      expect(storage.removeItem).toHaveBeenCalledWith("chunk-reload-/dashboard");
    } finally {
      process.removeListener("unhandledRejection", suppressHandler);
      vi.useRealTimers();
    }
  });
});
