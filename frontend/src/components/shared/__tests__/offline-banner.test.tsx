import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { OfflineBanner } from "@/components/shared/offline-banner";

// Mock lucide-react
vi.mock("lucide-react", () => ({
  WifiOff: (props: Record<string, unknown>) => (
    <span data-testid="wifi-off" {...props} />
  ),
}));

beforeEach(() => {
  // Default: online
  vi.stubGlobal("navigator", { ...navigator, onLine: true });
});

describe("OfflineBanner", () => {
  it("renders nothing when online", () => {
    const { container } = render(<OfflineBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("shows banner when offline event fires", () => {
    render(<OfflineBanner />);

    act(() => {
      window.dispatchEvent(new Event("offline"));
    });

    expect(
      screen.getByText(/you appear to be offline/i),
    ).toBeInTheDocument();
  });

  it("fades banner (opacity-0) when online event fires after being offline", () => {
    render(<OfflineBanner />);

    // Go offline
    act(() => {
      window.dispatchEvent(new Event("offline"));
    });

    const banner = screen.getByText(/you appear to be offline/i).closest(
      "div",
    );
    expect(banner?.className).toContain("opacity-100");

    // Come back online
    act(() => {
      window.dispatchEvent(new Event("online"));
    });

    expect(banner?.className).toContain("opacity-0");
  });
});
