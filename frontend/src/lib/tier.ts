import { TIER_DISPLAY_NAMES, TIER_LIMITS } from "./constants";

export function getTierDisplayName(tier: string): string {
  return TIER_DISPLAY_NAMES[tier] || tier;
}

export function getTierLimit(tier: string): number {
  return TIER_LIMITS[tier] || 1;
}

export const TIER_COMPARISON = [
  { tier: "free", name: "Free", maxRules: 5, price: "$0" },
  { tier: "starter", name: "Starter", maxRules: 2, price: "$9/mo" },
  { tier: "pro", name: "Pro", maxRules: 5, price: "$29/mo" },
  { tier: "elite", name: "Elite", maxRules: 15, price: "$79/mo" },
];
