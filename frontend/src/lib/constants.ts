export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "") + "/api/v1";
export const APP_NAME = "Signal Copier";

export const TIER_LIMITS: Record<string, number> = {
  free: 1,
  starter: 2,
  pro: 5,
  elite: 15,
};

export const TIER_DISPLAY_NAMES: Record<string, string> = {
  free: "Free",
  starter: "Starter",
  pro: "Pro",
  elite: "Elite",
};
