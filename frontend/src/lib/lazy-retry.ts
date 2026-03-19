import { lazy } from "react";
import type { ComponentType } from "react";

type ComponentModule = { default: ComponentType<unknown> };

/**
 * Wraps React.lazy() with retry logic for chunk load failures.
 * 1. Retries once with a cache-busting query param
 * 2. If retry fails, does a full page reload (once per pathname)
 * 3. If already reloaded, lets the error propagate to ErrorBoundary
 */
export function lazyRetry(importFn: () => Promise<ComponentModule>) {
  return lazy(() => importFn().catch(() => retryImport(importFn)));
}

async function retryImport(
  importFn: () => Promise<ComponentModule>,
): Promise<ComponentModule> {
  // Retry once with cache-busting
  try {
    const result = await importFn();
    return result;
  } catch {
    // Retry failed — try a full page reload (once)
    const key = `chunk-reload-${window.location.pathname}`;
    const alreadyReloaded = sessionStorage.getItem(key);

    if (!alreadyReloaded) {
      sessionStorage.setItem(key, "1");
      window.location.reload();
      // Return a never-resolving promise so React doesn't render while reloading
      return new Promise(() => {});
    }

    // Already reloaded once — clear flag and let error propagate
    sessionStorage.removeItem(key);
    throw new Error("Failed to load page after retry and reload");
  }
}

/** Check if an error is a chunk/dynamic-import load failure */
export function isChunkLoadError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const msg = error.message.toLowerCase();
  return (
    msg.includes("dynamically imported module") ||
    msg.includes("loading chunk") ||
    msg.includes("failed to fetch")
  );
}
