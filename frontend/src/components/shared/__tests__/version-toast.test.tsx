import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { VersionToast } from "@/components/shared/version-toast";

// Mock the hook
vi.mock("@/hooks/use-version-check", () => ({
  useVersionCheck: vi.fn(),
}));

import { useVersionCheck } from "@/hooks/use-version-check";
const mockUseVersionCheck = vi.mocked(useVersionCheck);

describe("VersionToast", () => {
  it("renders nothing when version is current", () => {
    mockUseVersionCheck.mockReturnValue({ stale: false });
    const { container } = render(<VersionToast />);
    expect(container.firstChild).toBeNull();
  });

  it("shows toast when version is stale", () => {
    mockUseVersionCheck.mockReturnValue({ stale: true });
    render(<VersionToast />);
    expect(screen.getByText("New version available")).toBeInTheDocument();
    expect(screen.getByText("Refresh now")).toBeInTheDocument();
  });
});
