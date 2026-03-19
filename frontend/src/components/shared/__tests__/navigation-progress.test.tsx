import { describe, it, expect, vi, afterEach } from "vitest";
import { render, act } from "@testing-library/react";
import { NavigationProgress } from "@/components/shared/navigation-progress";

afterEach(() => {
  vi.useRealTimers();
});

describe("NavigationProgress", () => {
  it("does not show immediately (200ms delay)", () => {
    vi.useFakeTimers();
    const { container } = render(<NavigationProgress />);
    // Before the 200ms timer fires, the fixed bar should not be present
    expect(container.querySelector(".fixed")).toBeNull();
  });

  it("shows the progress bar after the 200ms delay", () => {
    vi.useFakeTimers();
    const { container } = render(<NavigationProgress />);

    act(() => {
      vi.advanceTimersByTime(200);
    });

    const bar = container.querySelector(".fixed");
    expect(bar).not.toBeNull();
  });
});
