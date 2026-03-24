/** Format pip values consistently across marketplace components. */
export function fmtPips(v: number | null, sign = false): string {
  if (v === null) return "—";
  const prefix = sign && v > 0 ? "+" : "";
  const n = Math.abs(v) >= 1000
    ? v.toLocaleString(undefined, { maximumFractionDigits: 0 })
    : Number.isInteger(v) ? v.toString() : v.toFixed(1);
  return `${prefix}${n}p`;
}

export const ASSET_SHORT: Record<string, string> = {
  forex: "FX",
  crypto: "Crypto",
  both: "Multi",
};
