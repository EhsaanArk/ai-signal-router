import { describe, expect, it } from "vitest";
import { validateRequiredFields } from "../template-builder";
import type { MoneyManagementMode } from "../template-builder";

// Minimal V2 Forex template with all possible fields
const baseTemplate = {
  type: "",
  assistId: "test-id",
  source: "",
  symbol: "",
  date: "",
  takeProfits: [],
  stopLoss: null,
};

function makeJson(overrides: Record<string, unknown> = {}): string {
  return JSON.stringify({ ...baseTemplate, ...overrides });
}

describe("validateRequiredFields with MM mode", () => {
  // -----------------------------------------------------------------------
  // Field visibility: "default" mode hides balance AND lots
  // -----------------------------------------------------------------------
  describe("default mode", () => {
    it("does not require balance or lots", () => {
      const missing = validateRequiredFields(
        makeJson(),
        "sagemaster_forex",
        "V2",
        "default",
      );
      expect(missing).not.toContain("Balance");
      expect(missing).not.toContain("Lots");
    });
  });

  // -----------------------------------------------------------------------
  // "with_ratio" mode requires BOTH balance and lots
  // -----------------------------------------------------------------------
  describe("with_ratio mode", () => {
    it("reports balance and lots as missing when absent", () => {
      const missing = validateRequiredFields(
        makeJson(),
        "sagemaster_forex",
        "V2",
        "with_ratio",
      );
      expect(missing).toContain("Balance");
      expect(missing).toContain("Lots");
    });

    it("passes when balance and lots are present", () => {
      const missing = validateRequiredFields(
        makeJson({ balance: 1000, lots: 0.1 }),
        "sagemaster_forex",
        "V2",
        "with_ratio",
      );
      expect(missing).not.toContain("Balance");
      expect(missing).not.toContain("Lots");
    });
  });

  // -----------------------------------------------------------------------
  // "without_ratio" mode requires lots only, hides balance
  // -----------------------------------------------------------------------
  describe("without_ratio mode", () => {
    it("requires lots but not balance", () => {
      const missing = validateRequiredFields(
        makeJson(),
        "sagemaster_forex",
        "V2",
        "without_ratio",
      );
      expect(missing).toContain("Lots");
      expect(missing).not.toContain("Balance");
    });

    it("passes when lots is present", () => {
      const missing = validateRequiredFields(
        makeJson({ lots: 0.1 }),
        "sagemaster_forex",
        "V2",
        "without_ratio",
      );
      expect(missing).not.toContain("Lots");
    });
  });

  // -----------------------------------------------------------------------
  // "unsure" mode — shows all, requires nothing extra
  // -----------------------------------------------------------------------
  describe("unsure mode", () => {
    it("does not require balance or lots", () => {
      const missing = validateRequiredFields(
        makeJson(),
        "sagemaster_forex",
        "V2",
        "unsure",
      );
      expect(missing).not.toContain("Balance");
      expect(missing).not.toContain("Lots");
    });
  });

  // -----------------------------------------------------------------------
  // MM mode is ignored for non-V2-Forex contexts
  // -----------------------------------------------------------------------
  describe("non-V2-Forex contexts", () => {
    it("ignores MM mode for V1 Forex", () => {
      const missing = validateRequiredFields(
        JSON.stringify({ type: "", assistId: "id", source: "", symbol: "", date: "" }),
        "sagemaster_forex",
        "V1",
        "with_ratio",
      );
      // V1 doesn't have balance/lots fields at all
      expect(missing).not.toContain("Balance");
      expect(missing).not.toContain("Lots");
    });

    it("ignores MM mode for Crypto", () => {
      const crypto = {
        type: "",
        aiAssistId: "id",
        exchange: "binance",
        tradeSymbol: "",
        eventSymbol: "",
        date: "",
      };
      const missing = validateRequiredFields(
        JSON.stringify(crypto),
        "sagemaster_crypto",
        "V1",
        "with_ratio",
      );
      expect(missing).not.toContain("Balance");
      expect(missing).not.toContain("Lots");
    });

    it("ignores MM mode for custom destinations", () => {
      const missing = validateRequiredFields(
        makeJson(),
        "custom",
        "V2",
        "with_ratio",
      );
      expect(missing).toHaveLength(0); // custom = no required fields
    });
  });

  // -----------------------------------------------------------------------
  // No MM mode param = backward compatible (same as "unsure")
  // -----------------------------------------------------------------------
  describe("undefined MM mode (backward compatible)", () => {
    it("does not require balance or lots when mode is undefined", () => {
      const missing = validateRequiredFields(
        makeJson(),
        "sagemaster_forex",
        "V2",
      );
      expect(missing).not.toContain("Balance");
      expect(missing).not.toContain("Lots");
    });
  });
});
