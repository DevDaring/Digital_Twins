import type { GlucoseUnit } from "@/api/types";

/** mmol/L to mg/dL for glucose (the same factor the backend uses). */
export const MMOL_TO_MGDL = 18.016;

/** Plausible glucometer ranges per unit (anything outside is almost certainly a typo). */
export const UNIT_RANGE: Record<GlucoseUnit, { min: number; max: number; step: number; decimals: number }> = {
  "mg/dL": { min: 20, max: 600, step: 1, decimals: 0 },
  "mmol/L": { min: 1.1, max: 33.3, step: 0.1, decimals: 1 },
};

export function toMgdl(value: number, unit: GlucoseUnit): number {
  return unit === "mmol/L" ? value * MMOL_TO_MGDL : value;
}

/**
 * Parse what the user typed. Accepts a decimal comma ("5,6") and Indic digits; returns null for
 * anything that is not a single finite number.
 */
export function parseReading(raw: string): number | null {
  const indic: Record<string, string> = {};
  "०१२३४५६७८९".split("").forEach((c, i) => (indic[c] = String(i)));
  "০১২৩৪৫৬৭৮৯".split("").forEach((c, i) => (indic[c] = String(i)));
  "೦೧೨೩೪೫೬೭೮೯".split("").forEach((c, i) => (indic[c] = String(i)));
  const s = raw
    .trim()
    .split("")
    .map((c) => indic[c] ?? c)
    .join("")
    .replace(",", ".");
  if (!/^\d+(\.\d+)?$/.test(s)) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

export type ReadingCheck = { ok: true; value: number; mgdl: number } | { ok: false; reason: "empty" | "unit" | "format" | "range" };

/** Validate a manual reading. Both a value and an explicit unit are required. */
export function checkReading(raw: string, unit: GlucoseUnit | null): ReadingCheck {
  if (!raw.trim()) return { ok: false, reason: "empty" };
  if (!unit) return { ok: false, reason: "unit" };
  const v = parseReading(raw);
  if (v === null) return { ok: false, reason: "format" };
  const r = UNIT_RANGE[unit];
  if (v < r.min || v > r.max) return { ok: false, reason: "range" };
  return { ok: true, value: v, mgdl: toMgdl(v, unit) };
}
