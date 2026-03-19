import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorBoundary } from "@/components/shared/error-boundary";

// Mock Sentry
vi.mock("@sentry/react", () => ({
  captureException: vi.fn(),
}));

// Mock lucide-react icons to simple spans
vi.mock("lucide-react", () => ({
  AlertTriangle: (props: Record<string, unknown>) => (
    <span data-testid="alert-triangle" {...props} />
  ),
  Loader2: (props: Record<string, unknown>) => (
    <span data-testid="loader" {...props} />
  ),
}));

import * as Sentry from "@sentry/react";

// Helper that throws on render
function ThrowError({ error }: { error: Error }) {
  throw error;
}

// Suppress React error boundary console.error noise in tests
const originalError = console.error;
beforeEach(() => {
  console.error = vi.fn();
  vi.stubGlobal("sessionStorage", {
    getItem: vi.fn(() => null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
    length: 0,
    key: vi.fn(() => null),
  });
  vi.stubGlobal("location", {
    ...window.location,
    pathname: "/test",
    reload: vi.fn(),
  });
  return () => {
    console.error = originalError;
  };
});

describe("ErrorBoundary", () => {
  it('shows "Updating to latest version..." for chunk load errors', () => {
    const chunkError = new Error(
      "Failed to fetch dynamically imported module: /chunk-abc.js",
    );

    render(
      <ErrorBoundary>
        <ThrowError error={chunkError} />
      </ErrorBoundary>,
    );

    expect(
      screen.getByText("Updating to latest version..."),
    ).toBeInTheDocument();
  });

  it('shows "Something went wrong" for generic errors', () => {
    const genericError = new Error("Unexpected error");

    render(
      <ErrorBoundary>
        <ThrowError error={genericError} />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("reports chunk errors to Sentry with correct tag", () => {
    const chunkError = new Error(
      "Failed to fetch dynamically imported module: /chunk-abc.js",
    );

    render(
      <ErrorBoundary>
        <ThrowError error={chunkError} />
      </ErrorBoundary>,
    );

    expect(Sentry.captureException).toHaveBeenCalledWith(
      chunkError,
      expect.objectContaining({
        tags: { type: "chunk_load_error" },
      }),
    );
  });

  it("reports generic errors to Sentry without chunk tag", () => {
    const genericError = new Error("Unexpected error");

    render(
      <ErrorBoundary>
        <ThrowError error={genericError} />
      </ErrorBoundary>,
    );

    expect(Sentry.captureException).toHaveBeenCalledWith(
      genericError,
      expect.objectContaining({
        contexts: expect.objectContaining({
          react: expect.any(Object),
        }),
      }),
    );
    // Should NOT have the chunk tag
    expect(Sentry.captureException).not.toHaveBeenCalledWith(
      genericError,
      expect.objectContaining({
        tags: { type: "chunk_load_error" },
      }),
    );
  });
});
