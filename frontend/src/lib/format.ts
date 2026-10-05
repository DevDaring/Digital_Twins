import type { TFunction } from "i18next";
import type { Lang } from "@/api/types";

/** Intl locale with Western digits for every UI language (keeps numbers consistent across scripts). */
export const intlLocale = (lang: Lang | string) => `${lang}-u-nu-latn`;

/** Parse contract times. ISO strings without an offset are local time (Asia/Kolkata replay clock). */
export function parseTime(iso: string): Date {
  // Clock-only values ("06:30", used by the daily profile) map onto a fixed reference day.
  const hm = /^(\d{1,2}):(\d{2})$/.exec(iso);
  if (hm) return new Date(2000, 0, 1, Number(hm[1]), Number(hm[2]));
  return new Date(iso);
}

export function formatClock(iso: string | Date, lang: Lang | string): string {
  const d = typeof iso === "string" ? parseTime(iso) : iso;
  return new Intl.DateTimeFormat(intlLocale(lang), { hour: "numeric", minute: "2-digit" }).format(d);
}

export function formatHour(d: Date, lang: Lang | string): string {
  return new Intl.DateTimeFormat(intlLocale(lang), { hour: "numeric" }).format(d);
}

export function formatDateTime(iso: string, lang: Lang | string): string {
  const d = parseTime(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(intlLocale(lang), { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }).format(d);
}

/** 0..1 → whole percent. */
export const pct = (p: number) => Math.round(p * 100);

/** Number of times out of 10 for a probability. */
export const outOfTen = (p: number) => Math.round(Math.min(1, Math.max(0, p)) * 10);

/** Probability as a localised natural frequency: "about 7 times out of 10". */
export function freqText(t: TFunction, p: number): string {
  if (!Number.isFinite(p)) return "";
  if (p < 0.05) return t("freq.rare");
  if (p >= 0.95) return t("freq.always");
  return t("freq.n", { count: outOfTen(p) });
}

export const signed = (n: number, digits = 0) => {
  const v = Number(n.toFixed(digits));
  return `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v).toFixed(digits)}`;
};

export const round1 = (n: number) => Math.round(n * 10) / 10;

/** Format a metric that may be a fraction (0..1) as a percent, else as-is. */
export function fmtMetric(v: unknown, key = ""): string {
  if (typeof v === "number") {
    if (!Number.isFinite(v)) return "—";
    const looksRate = /rate|coverage|auroc|auprc|tir|share|frac|ece|pct|zone/i.test(key);
    if (looksRate && v >= 0 && v <= 1 && !/auroc|auprc|ece/i.test(key)) return `${(v * 100).toFixed(v * 100 < 10 ? 1 : 0)}%`;
    if (Number.isInteger(v)) return String(v);
    return Math.abs(v) < 1 ? v.toFixed(2) : v.toFixed(1);
  }
  if (typeof v === "boolean") return v ? "✓" : "—";
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}

const MEAL_NAMES = ["breakfast", "lunch", "dinner", "snack"];
/** Localise the generic meal names the backend logs ("Lunch", "Snack", ...); other names pass through. */
export function mealName(t: TFunction, name: string | undefined | null): string {
  const k = (name ?? "").trim().toLowerCase();
  return MEAL_NAMES.includes(k) ? t(`mealNames.${k}`) : (name ?? "");
}

/**
 * Display text for a food swap: the backend's localised `label` when it really is localised,
 * else the English label (flagged so the caller can set lang="en" on it).
 */
export function swapLabel(sw: { label?: string; label_en: string }, lang: string): { text: string; english: boolean } {
  if (sw.label && (lang === "en-IN" || sw.label !== sw.label_en)) return { text: sw.label, english: false };
  return { text: sw.label_en, english: lang !== "en-IN" };
}
