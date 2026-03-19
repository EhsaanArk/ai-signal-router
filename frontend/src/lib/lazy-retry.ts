import { lazy } from "react";
import type { ComponentType } from "react";

type ComponentModule = { default: ComponentType<unknown> };

/** SessionStorage key for chunk reload guard — shared between lazy-retry and error-boundary */
export function getChunkReloadKey(pathname?: string): string {
  return `chunk-reload-${pathname ?? window.location.pathname}`;
}

/**
 * Wraps React.lazy() with retry logic for chunk load failures.
 * 1. Retries once after a brief delay (handles transient network errors)
 * 2. If retry fails, does a full page reload (once per pathname)
 * 3. If already reloaded, lets the error propagate to ErrorBoundary
 */
export function lazyRetry(importFn: () => Promise<ComponentModule>) {
  return lazy(() => importFn().catch(() => retryImport(importFn)));
}

async function retryImport(
  importFn: () => Promise<ComponentModule>,
): Promise<ComponentModule> {
  // Retry after a brief delay — helps with transient network errors
  await new Promise((resolve) => setTimeout(resolve, 500));
  try {
    const result = await importFn();
    // Success on retry — clear any previous reload flag
    sessionStorage.removeItem(getChunkReloadKey());
    return result;
  } catch {
    // Retry failed — try a full page reload (once per pathname)
    const key = getChunkReloadKey();
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
    msg.includes("importing a module script") ||
    msg.includes("loading chunk") ||
    msg.includes("loading css chunk")
  );
}
