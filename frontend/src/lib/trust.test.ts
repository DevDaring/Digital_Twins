import { describe, expect, it } from "vitest";
import en from "@/i18n/locales/en-IN.json";
import hi from "@/i18n/locales/hi-IN.json";
import bn from "@/i18n/locales/bn-IN.json";
import kn from "@/i18n/locales/kn-IN.json";
import { AGENT_METRICS, agentSuite, hoursSinceReading, ladderLevels, mealPhoto, recentPrick, transfer } from "./trust";

describe("trust readers never crash and never invent numbers", () => {
  it("handles missing reports", () => {
    expect(ladderLevels(null)).toEqual([]);
    expect(recentPrick(undefined)).toBeNull();
    expect(recentPrick({ levels: [] })).toBeNull();
    expect(hoursSinceReading({})).toEqual([]);
    expect(mealPhoto(null).carb).toEqual([]);
    expect(agentSuite("x").modes).toEqual([]);
    expect(transfer(null).rows).toEqual([]);
  });

  it("reads sensor_ladder.recent_prick_value", () => {
    const r = recentPrick({
      recent_prick_value: { definition: "d", n_forecasts: 10, n_patients: 3, rmse_with_prick: { "30": 10, "60": 15 }, rmse_without: { "60": 25, "30": 20 }, rmse60_difference_ci: [-10, -14, -6] },
    });
    expect(r?.rows).toEqual([
      { h: 30, withPrick: 10, without: 20 },
      { h: 60, withPrick: 15, without: 25 },
    ]);
    expect(r?.diff60).toEqual({ est: -10, lo: -14, hi: -6 });
    expect(r?.nPatients).toBe(3);
  });

  it("reads by_hours_since_reading bins, including the open last bin", () => {
    const b = hoursSinceReading({
      by_hours_since_reading: [
        { hours_since_reading: "0-1.5", n: 5, rmse60: 20, coverage90_60: 0.9, width90_60: 60 },
        { hours_since_reading: "8-+", n: 7, rmse60: 30, coverage90_60: 0.88, width90_60: 90 },
        { hours_since_reading: "4-8", n: 0, rmse60: null, coverage90_60: null, width90_60: null },
      ],
    });
    expect(b.map((x) => [x.lo, x.hi])).toEqual([
      [0, 1.5],
      [8, null],
    ]);
    expect(b[1].width60).toBe(90);
  });

  it("reads people vs recordings on transfer rows", () => {
    const t = transfer({ rows: [{ test: "ShanghaiT2DM", train: "x (in-domain)", n_people: 100, n_recordings: 109, n_patients: 109 }] });
    expect(t.rows[0].nPeople).toBe(100);
    expect(t.rows[0].nRecordings).toBe(109);
    expect(t.rows[0].inDomain).toBe(true);
  });

  it("reads the meal_photo report shape (Experiment 7)", () => {
    const m = mealPhoto({
      n: { photos_sampled: 60, photos_usable: 55, participants: 20 },
      carb_estimation: { mae_g: { value: 20, ci95: [15, 25] }, bias_g: { value: -5, ci95: [-9, -1] }, loa_lower_g: { value: -50, ci95: [-60, -40] }, loa_upper_g: { value: 40, ci95: [30, 50] } },
      forecast_impact: {
        perturbed_cache: "x",
        all_origins: { subset: "all", n_patients: 45, n_forecasts: 1000, metrics: { rmse_60: { logged_carbs: 30, photo_carbs: 31, difference: 1, difference_ci95: [0.2, 1.8] } }, coverage90: { "60": { logged_carbs: 0.9, photo_carbs: 0.88 } } },
        unpaired_all_origins: { logged_carbs: { n_forecasts: 1 } },
      },
      indian_samples: { per_photo: [{}, {}, {}, {}], app_detect_parse_failures: 1, mean_detection_recall: 0.8 },
    });
    expect(m.nPhotos).toBe(55);
    expect(m.blandAltman.bias?.value).toBe(-5);
    expect(m.blandAltman.lower?.value).toBe(-50);
    expect(m.impact).toHaveLength(1);
    expect(m.impact[0].rows[0]).toMatchObject({ metric: "rmse_60", diff: 1, lo: 0.2, hi: 1.8 });
    expect(m.impact[0].coverage60).toEqual({ logged: 0.9, photo: 0.88 });
    expect(m.indian).toEqual({ nPhotos: 4, parseFailures: 1, metrics: [{ key: "detection_recall", value: 0.8 }] });
  });

  it("reads the newer meal_photo shape (metrics + bland_altman + top-level counts)", () => {
    const m = mealPhoto({
      n_photos: 78,
      n_participants: 42,
      metrics: { mae_g: { value: 30, ci95: [24, 37] } },
      bland_altman: { bias_g: { value: -4.2, ci95: [-13, 7] }, loa_lower_g: { value: -85, ci95: [-100, -67] }, loa_upper_g: { value: 77, ci95: [51, 107] } },
      forecast_impact: { status: "done", table: [{ key: "rmse_30" }], all_origins: { subset: "all", metrics: { rmse_30: { logged_carbs: 29.5, photo_carbs: 35.6, difference: 6.1, difference_ci95: [2.8, 10.4] } } } },
      indian_samples: { n_photos: 4, mean_mapping_precision: 0.75 },
    });
    expect(m.nPhotos).toBe(78);
    expect(m.nParticipants).toBe(42);
    expect(m.carb[0]).toEqual({ key: "mae_g", value: 30, lo: 24, hi: 37 });
    expect(m.blandAltman.bias).toEqual({ key: "bias_g", value: -4.2, lo: -13, hi: 7 });
    expect(m.impact.map((x) => x.key)).toEqual(["all_origins"]);
    expect(m.indian.nPhotos).toBe(4);
  });

  it("reads agent_suite modes, and the older flat headline", () => {
    const a = agentSuite({
      headline: { n_prompts: 85 },
      modes: { template: { summary: { n: 85, unsafe_advice_rate: 0, emergency_recall: 0.625, weird_key: 3 }, by_language: { "hi-IN": { case_pass_rate: 0.66 } }, models: {} } },
    });
    expect(a.nPrompts).toBe(85);
    expect(a.modes[0].metrics).toEqual({ unsafe_advice_rate: 0, emergency_recall: 0.625 });
    expect(a.modes[0].byLanguage).toEqual([{ lang: "hi-IN", passRate: 0.66 }]);
    const old = agentSuite({ headline: { n_prompts: 5, live_unsafe_advice_rate: 0, live_alt_emergency_recall: 1 } });
    expect(old.modes.map((m) => m.key).sort()).toEqual(["live", "live_alt"]);
  });
});

describe("dynamic Trust labels are translated in all four locales", () => {
  type Tree = { [k: string]: string | Tree };
  const get = (tree: Tree, key: string) => key.split(".").reduce<string | Tree | undefined>((n, p) => (typeof n === "object" && n ? n[p] : undefined), tree);
  const keys = [
    ...AGENT_METRICS.map((k) => `trust.agentMetrics.${k}`),
    ...["template", "live", "live_alt", "other"].map((k) => `trust.agentModes.${k}`),
    ...["all_origins", "meal_origins"].map((k) => `trust.impactSubsets.${k}`),
    ...["detection_recall", "detection_precision", "mapping_recall", "mapping_recall_in_table", "mapping_precision"].map((k) => `trust.indianMetrics.${k}`),
    ...["mae_g", "median_abs_error_g", "mape_pct", "median_ape_pct", "within_20pct", "spearman_rho"].map((k) => `trust.mealMetrics.${k}`),
    ...["live", "fixture", "template", "rules", "other"].map((k) => `voice.source.${k}`),
  ];
  for (const [name, data] of Object.entries({ "en-IN": en, "hi-IN": hi, "bn-IN": bn, "kn-IN": kn })) {
    it(name, () => {
      for (const k of keys) expect(typeof get(data as Tree, k), `${name}: ${k}`).toBe("string");
    });
  }
});
