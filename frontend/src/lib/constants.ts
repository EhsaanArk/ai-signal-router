export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "") + "/api/v1";
export const APP_NAME = "Sage Radar AI";

export const TIER_LIMITS: Record<string, number> = {
  free: 5,
  starter: 2,
  pro: 5,
  elite: 15,
};

export const BETA_DISABLED_MSG =
  "Thanks for being part of the beta program! We are working towards the big launch — stay tuned!";

export const TIER_DISPLAY_NAMES: Record<string, string> = {
  free: "Free",
  starter: "Starter",
  pro: "Pro",
  elite: "Elite",
};
