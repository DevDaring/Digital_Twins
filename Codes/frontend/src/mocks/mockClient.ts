// Offline mock implementation of the full ApiClient. Loaded lazily (own chunk) only when
// VITE_MOCK=1 or when the backend is unreachable at login time.
import type {
  AgentReply,
  ApiClient,
  Assimilation,
  Band,
  Food,
  LabField,
  Lang,
  Ladder,
  MealDish,
  MealInput,
  MealParse,
  QueueItem,
  Receipt,
  ReceiptClaim,
  ReviewState,
  Scenario,
  TwinState,
} from "@/api/types";
import { receiptToMarkdown } from "@/lib/evidence";
import { ApiError } from "@/api/http";
import { mockChat, pendingActions } from "./agent";
import { assessReading } from "./safety";
import { buildBody } from "./body";
import {
  FOODS,
  LAB_FIELDS,
  LAB_SAMPLES,
  MEAL_SAMPLES,
  MEAL_SAMPLE_DISHES,
  SWAPS,
  TOUR,
  VOICE_SAMPLES,
  allPatients,
  patientDetail,
} from "./data";
import {
  MAX_OFFSET_MIN,
  NOW,
  buildForecast,
  buildNbp,
  buildState,
  extraReadings,
  fmtLocal,
  forecastDrivers,
  forecastStore,
  modelById,
  nowOf,
  referenceAt,
  replayOffsets,
  resetPersona,
  weekStats,
} from "./sim";

const wait = (min = 220, max = 560) => new Promise((r) => setTimeout(r, min + Math.random() * (max - min)));
const r1 = (v: number) => Math.round(v * 10) / 10;
const food = (id: string) => FOODS.find((f) => f.id === id);

const DEMO_USERS: Record<string, { display_name: string; roles: ("patient" | "clinician")[] }> = {
  devtester: { display_name: "Dev Tester", roles: ["patient", "clinician"] },
  testuser: { display_name: "Test User", roles: ["patient", "clinician"] },
};

const confirmed = new Map<string, LabField[]>();
const reviews = new Map<string, ReviewState>();
const idempotent = new Map<string, Assimilation>();

const width = (b: Band) => b.hi - b.lo;
/** Width of the 90% forecast band 2 h after the origin. */
function width120(s: TwinState): number {
  const q = s.forecast.traj;
  const i = Math.min(q.t.length - 1, 24);
  return q.q95[i] - q.q05[i];
}
const signedPct = (b: number, a: number) => (b > 0 ? Math.round(((a - b) / b) * 1000) / 10 : 0);

/** Add an observation to the mock twin and report the change exactly as contract v3 does. */
function addObservation(pid: string, ladder: Ladder, mgdl: number, at: string, lang: Lang): Assimilation {
  const model = modelById(pid);
  const before = buildState(model, ladder);
  const list = extraReadings.get(pid) ?? [];
  extraReadings.set(pid, [...list.filter((r) => r.t !== at), { t: at, value: Math.round(mgdl), kind: "fingerprick" }]);
  const after = buildState(model, ladder);
  const now = { before: width(before.band), after: width(after.band), signed_pct: signedPct(width(before.band), width(after.band)), horizon_min: 0 };
  const h120 = { before: Math.round(width120(before)), after: Math.round(width120(after)), signed_pct: signedPct(width120(before), width120(after)), horizon_min: 120 };
  return {
    state: after,
    band_before: before.band,
    band_after: after.band,
    narrowed_pct: -h120.signed_pct,
    innovation: Math.round(mgdl - before.estimate),
    safety: assessReading(mgdl, lang),
    width_change: { now, h120 },
  };
}

function staleError(lang: Lang) {
  const msg: Record<Lang, string> = {
    "en-IN": "This reading is more than 30 minutes away from the replay time, so it cannot be added as a current reading.",
    "hi-IN": "यह रीडिंग रीप्ले समय से 30 मिनट से ज़्यादा दूर है, इसलिए इसे अभी की रीडिंग के रूप में नहीं जोड़ा जा सकता।",
    "bn-IN": "এই রিডিং রিপ্লে সময় থেকে 30 মিনিটের বেশি দূরে, তাই এটাকে এখনকার রিডিং হিসেবে যোগ করা যাবে না।",
    "kn-IN": "ಈ ರೀಡಿಂಗ್ ರೀಪ್ಲೇ ಸಮಯದಿಂದ 30 ನಿಮಿಷಕ್ಕಿಂತ ಹೆಚ್ಚು ದೂರವಿದೆ, ಆದ್ದರಿಂದ ಇದನ್ನು ಈಗಿನ ರೀಡಿಂಗ್ ಆಗಿ ಸೇರಿಸಲಾಗುವುದಿಲ್ಲ.",
  };
  return new ApiError(422, msg[lang], { detail: { code: "stale_observation", message: msg[lang] } });
}

function dishFrom(spec: (typeof MEAL_SAMPLE_DISHES)[string][number]): MealDish {
  const f = spec.food_id ? food(spec.food_id) : undefined;
  const cands = spec.candidates?.map((c) => food(c)).filter(Boolean) as Food[] | undefined;
  const ref = f ?? cands?.[0];
  const u = spec.units;
  return {
    food_id: f?.id ?? null,
    detected: spec.detected,
    name: f?.name ?? spec.detected,
    units: u,
    unit: ref?.unit ?? "katori",
    carbs: r1((ref?.carbs_g ?? 12) * u),
    fibre: r1((ref?.fibre_g ?? 2) * u),
    protein: r1((ref?.protein_g ?? 4) * u),
    fat: r1((ref?.fat_g ?? 6) * u),
    confidence: spec.confidence,
    needs_pick: !f,
    candidates: cands,
  };
}

function parseFor(sampleId: string): MealParse {
  const specs = MEAL_SAMPLE_DISHES[sampleId] ?? MEAL_SAMPLE_DISHES.north_indian_thali;
  const dishes = specs.map(dishFrom);
  const sum = (k: "carbs" | "fibre" | "protein" | "fat") => r1(dishes.reduce((a, d) => a + d[k], 0));
  const total = { carbs: sum("carbs"), fibre: sum("fibre"), protein: sum("protein"), fat: sum("fat"), kcal: 0 };
  total.kcal = Math.round(total.carbs * 4 + total.protein * 4 + total.fat * 9);
  const carbs_sd = r1(Math.sqrt(dishes.reduce((a, d) => a + (d.carbs * (1 - d.confidence) * 0.8) ** 2, 0)) + 4);
  return { dishes, total, carbs_sd, source: "fixture" };
}

function applyScenario(baseMeal: MealInput, scenario: Scenario) {
  const meal = { ...baseMeal };
  let carbs = meal.carbs * (scenario.carb_scale ?? 1);
  if (scenario.swap) {
    const sw = SWAPS.find((s) => s.from === scenario.swap?.from && s.to === scenario.swap?.to);
    const item = meal.items?.find((i) => i.food_id === scenario.swap?.from);
    const from = food(scenario.swap.from);
    const to = food(scenario.swap.to);
    if (item && from && to) {
      // Keep roughly the same plate volume: convert by grams.
      const toUnits = (item.units * from.grams_per_unit) / to.grams_per_unit;
      carbs = carbs - from.carbs_g * item.units * (scenario.carb_scale ?? 1) + Math.min(to.carbs_g * toUnits, from.carbs_g * item.units * 0.85) * (scenario.carb_scale ?? 1);
      meal.fibre = (meal.fibre ?? 0) + (to.fibre_g * toUnits - from.fibre_g * item.units);
    } else {
      carbs *= sw?.factor ?? 0.88;
      meal.fibre = (meal.fibre ?? 0) + 2;
    }
  }
  meal.carbs = Math.max(0, carbs);
  meal.minutes_from_now = Math.max(0, (meal.minutes_from_now ?? 15) + (scenario.shift_min ?? 0));
  return {
    meal,
    walk: scenario.walk_min ? { minutes: scenario.walk_min, afterMealMin: scenario.walk_after_min ?? 10 } : undefined,
    gainScale: 1 + Math.min(0, scenario.shift_min ?? 0) / 1500,
  };
}

export const mockClient: ApiClient = {
  async login(username, password) {
    await wait(400, 800);
    const u = DEMO_USERS[username.trim().toLowerCase()];
    if (!u || !password) throw new ApiError(401, "Invalid username or password");
    return { access_token: `mock-${username}-${Date.now()}`, user: { username: username.trim(), ...u } };
  },
  async me() {
    return { username: "DevTester", ...DEMO_USERS.devtester };
  },
  async health() {
    return { ok: true, mode: "demo" };
  },
  async patients() {
    await wait();
    return allPatients();
  },
  async patient(pid) {
    await wait();
    return patientDetail(pid);
  },
  async twinState(pid, ladder) {
    await wait(260, 620);
    return buildState(modelById(pid), ladder);
  },
  async forecast(pid, body) {
    await wait();
    return buildForecast(modelById(pid), body.ladder, { meal: body.meal, horizonMin: body.horizon_min });
  },
  async whatIf(pid, body) {
    await wait(300, 650);
    const model = modelById(pid);
    const baseMeal = { minutes_from_now: 15, ...body.base_meal };
    const baseline = buildForecast(model, body.ladder, { meal: baseMeal });
    const sc = applyScenario(baseMeal, body.scenario);
    const scenario = buildForecast(model, body.ladder, { meal: { ...sc.meal, carbs: sc.meal.carbs * sc.gainScale }, walk: sc.walk });
    const mean = Math.round((scenario.p_high.p - baseline.p_high.p) * 100) / 100;
    const half = Math.round((0.05 + Math.abs(mean) * 0.35) * 100) / 100;
    const lo = Math.round((mean - half) * 100) / 100;
    const hi = Math.round((mean + half) * 100) / 100;
    const tooSmall = Math.abs(mean) < 0.05 || (lo < 0 && hi > 0);
    return {
      baseline,
      scenario,
      delta_p_high: { mean, lo, hi },
      delta_peak: scenario.peak.value - baseline.peak.value,
      too_small_to_call: tooSmall,
      note: tooSmall
        ? "The difference is inside the twin's uncertainty, so it is too small to call."
        : "The difference is larger than the twin's uncertainty.",
    };
  },
  async body(pid, body) {
    await wait(240, 520);
    if (body.scenario && !body.meal) throw new ApiError(422, "A scenario needs the meal it changes (meal).", { detail: "A scenario needs the meal it changes (meal)." });
    const model = modelById(pid);
    const st = buildState(model, body.ladder);
    const meal = body.meal ? { minutes_from_now: 15, ...body.meal } : undefined;
    const base = buildForecast(model, body.ladder, { meal });
    let scen = null;
    if (meal && body.scenario) {
      const sc = applyScenario(meal, body.scenario);
      scen = buildForecast(model, body.ladder, { meal: { ...sc.meal, carbs: sc.meal.carbs * sc.gainScale }, walk: sc.walk });
    }
    return buildBody(pid, { ...body, meal }, base.origin, base, scen, st.estimate);
  },
  async nextBestPrick(pid, ladder) {
    await wait();
    return buildNbp(modelById(pid), ladder);
  },
  async assimilate(pid, body, lang = "en-IN"): Promise<Assimilation> {
    await wait(380, 700);
    if (body.idempotency_key && idempotent.has(body.idempotency_key)) return idempotent.get(body.idempotency_key) as Assimilation;
    if (body.unit !== "mg/dL" && body.unit !== "mmol/L") throw new ApiError(422, "unit is required", { detail: "unit is required" });
    const now = nowOf(pid);
    const at = body.observed_at ?? fmtLocal(now);
    if (Math.abs(new Date(at).getTime() - now.getTime()) > 30 * 60_000) throw staleError(lang);
    const mgdl = body.unit === "mmol/L" ? body.value * 18.016 : body.value;
    const res = addObservation(pid, body.ladder, mgdl, at, lang);
    if (body.idempotency_key) idempotent.set(body.idempotency_key, res);
    return res;
  },
  async advance(pid, body) {
    await wait(260, 520);
    if (!(body.minutes >= 15 && body.minutes <= 240)) throw new ApiError(422, "minutes must be 15..240", { detail: "minutes must be 15..240" });
    replayOffsets.set(pid, Math.min(MAX_OFFSET_MIN, (replayOffsets.get(pid) ?? 0) + body.minutes));
    return buildState(modelById(pid), body.ladder);
  },
  async reveal(pid, body, lang = "en-IN") {
    await wait(320, 600);
    const model = modelById(pid);
    const st = buildState(model, body.ladder);
    const ref = referenceAt(model);
    return {
      reference: { ...ref, source_en: "Dataset reference CGM — hidden from the twin until revealed" },
      before: { estimate: st.estimate, band: st.band, forecast_peak: st.forecast.peak, p_high: st.forecast.p_high },
      after: body.assimilate ? addObservation(pid, body.ladder, ref.value, ref.t, lang) : null,
    };
  },
  async receipt(pid, fid) {
    await wait(200, 400);
    const hit = forecastStore.get(fid);
    if (!hit || hit.pid !== pid) throw new ApiError(404, "Forecast not found", { detail: "Forecast not found" });
    return mockReceipt(pid, hit.forecast);
  },
  async receiptMarkdown(pid, fid) {
    const r = await mockClient.receipt(pid, fid, "en-IN");
    return receiptToMarkdown(r, { title: "Pratifalan evidence receipt (offline mock)", status: (x) => x, claim: "Claim", value: "Value", source: "Source" });
  },
  async outlook(pid) {
    await wait();
    const p = patientDetail(pid);
    const days = Array.from({ length: 14 }, (_, i) => i * 7);
    const ease = (i: number) => 1 - Math.exp(-i / 4);
    return {
      label: "projection",
      days,
      tir_current: days.map((_, i) => r1((p.tir_7d - 0.015 * (i / 13)) * 100) / 100),
      tir_scenario: days.map((_, i) => r1((p.tir_7d + 0.09 * ease(i)) * 100) / 100),
      ehba1c_current: days.map((_, i) => r1(p.hba1c + 0.12 * (i / 13))),
      ehba1c_scenario: days.map((_, i) => r1(p.hba1c - 0.35 * ease(i))),
      scenario_label: "15-minute walk after dinner",
      note: "Projection if today's habits continue, versus adopting the top what-if change. Not a prediction of lab results.",
    };
  },
  async explain(_pid, forecastId) {
    await wait();
    const drivers = forecastDrivers.get(forecastId) ?? [];
    return {
      physiology: drivers.filter((d) => d.source === "physiology"),
      learned: drivers.filter((d) => d.source === "learned"),
      tool_calls: [{ name: "explain", args: { forecast_id: forecastId }, output: { n_drivers: drivers.length } }],
      text_en: drivers.length
        ? `The biggest driver is "${drivers[0].label_en}" (${drivers[0].contribution > 0 ? "+" : ""}${drivers[0].contribution} mg/dL at 2 hours).`
        : "No drivers recorded for this forecast.",
    };
  },
  async resetTwin(pid) {
    await wait(150, 300);
    resetPersona(pid);
    confirmed.delete(pid);
    return { ok: true };
  },
  async ready() {
    return { ok: true, db: true, model: "offline mock" };
  },
  async foodSearch(q) {
    await wait(120, 260);
    const s = q.trim().toLowerCase();
    return FOODS.filter((f) => f.name_en.toLowerCase().includes(s) || f.id.includes(s) || f.cuisine.toLowerCase().includes(s)).slice(0, 8);
  },
  async foodSwaps(lang) {
    await wait(100, 200);
    // The mock has English labels only; `label` is English unless the UI language is English anyway.
    return SWAPS.map(({ from, to, label_en }) => ({ from, to, label_en, ...(lang === "en-IN" ? { label: label_en } : {}) }));
  },
  async mealSamples() {
    await wait(100, 200);
    return MEAL_SAMPLES;
  },
  async mealPhoto(input) {
    await wait(1100, 1700);
    return parseFor("sample_id" in input ? input.sample_id : "north_indian_thali");
  },
  async agentChat(body, signal) {
    await wait(700, 1200);
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
    return mockChat(body);
  },
  async agentConfirm(body) {
    await wait(400, 700);
    const act = pendingActions.get(body.action_id);
    if (!act) throw new ApiError(404, "Unknown action", { detail: "Unknown action" });
    pendingActions.delete(body.action_id);
    const lang = act.lang;
    const base: Omit<AgentReply, "reply" | "intent"> = {
      lang,
      tool_calls: [],
      grounding: { passed: true, numbers: [], fallback_used: false },
      safety: { blocked: false, emergency: false, reason: null },
      highlight: { view: "stage" },
      audio_url: null,
      source: "fixture",
      source_detail: "rules",
      claims: [],
      pending_action: null,
    };
    if (!body.confirm) return { ...base, reply: CANCELLED[lang], intent: "cancelled", highlight: { view: "none" } };
    if (act.kind === "log_reading") {
      const value = Number(act.payload.value);
      const unit = act.payload.unit === "mmol/L" ? "mmol/L" : "mg/dL";
      const mgdl = unit === "mmol/L" ? value * 18.016 : value;
      const res = addObservation(act.pid, act.ladder, mgdl, fmtLocal(nowOf(act.pid)), lang);
      const safety = res.safety!;
      return {
        ...base,
        reply: safety.level === "ok" ? LOGGED[lang] : `${safety.title}. ${safety.message}`,
        intent: "log_reading",
        tool_calls: [{ name: "assimilate", args: { value, unit, source: "chat" }, output: { safety, width_change: res.width_change } }],
        safety: { blocked: false, emergency: safety.emergency, reason: safety.level === "ok" ? null : `${safety.level}_reading` },
        claims: [{ slot: "reading", field: "assimilate.value", value: Math.round(mgdl), rendered: String(Math.round(mgdl)) }],
      };
    }
    return { ...base, reply: LOGGED[lang], intent: "log_meal" };
  },
  async stt() {
    await wait(200, 300);
    // No offline speech model: the UI falls back to the browser's Web Speech API.
    throw new ApiError(404, "Speech-to-text is not available offline");
  },
  async tts() {
    return null;
  },
  async voiceSamples() {
    await wait(100, 200);
    return VOICE_SAMPLES;
  },
  async labSamples() {
    await wait(100, 200);
    return LAB_SAMPLES;
  },
  async labParse() {
    await wait(1200, 1800);
    return { fields: LAB_FIELDS.map((f) => ({ ...f })), source: "fixture" };
  },
  async labConfirm(patientId, fields) {
    await wait(400, 700);
    confirmed.set(patientId, fields);
    return { bundle_id: `mock-bundle-${patientId}-${Date.now().toString(36)}`, resource_count: fields.length + 1 };
  },
  async fhirBundle(pid) {
    await wait(150, 300);
    const fields = confirmed.get(pid) ?? [];
    return {
      resourceType: "Bundle",
      type: "collection",
      meta: { tag: [{ code: "offline-mock", display: "Offline mock: not a real record" }] },
      entry: [
        { resource: { resourceType: "Patient", id: pid, meta: { tag: [{ code: "synthetic" }] } } },
        ...fields.map((f, i) => ({
          resource:
            typeof f.value === "number"
              ? {
                  resourceType: "Observation",
                  id: `obs-${i}`,
                  status: "final",
                  code: { coding: f.loinc ? [{ system: "http://loinc.org", code: f.loinc, display: f.name }] : [], text: f.name },
                  subject: { reference: `Patient/${pid}` },
                  valueQuantity: { value: f.value, unit: f.unit },
                }
              : {
                  resourceType: "MedicationStatement",
                  id: `med-${i}`,
                  status: "active",
                  medicationCodeableConcept: { text: String(f.value) },
                  subject: { reference: `Patient/${pid}` },
                },
        })),
      ],
    };
  },
  async doctorPanel() {
    await wait();
    return allPatients()
      .map(withOperational)
      .sort((a, b) => b.risk_7d - a.risk_7d);
  },
  async doctorQueue() {
    await wait();
    return allPatients().map((p): QueueItem => {
      const st = buildState(modelById(p.id), "2");
      const reasons: QueueItem["reasons"] = [];
      if (st.freshness.hours_since_reading >= 8) reasons.push({ kind: "missing_data", detail_en: `No glucose reading for ${st.freshness.hours_since_reading.toFixed(1)} h (2 pricks a day).` });
      const extremes = (extraReadings.get(p.id) ?? []).filter((r) => r.value < 70 || r.value > 300);
      if (extremes.length) reasons.push({ kind: "concerning_observation", detail_en: `Reading of ${extremes[extremes.length - 1].value} mg/dL logged.` });
      if (st.forecast.p_high.p >= 0.5) reasons.push({ kind: "model_risk", detail_en: `Model: about ${Math.round(st.forecast.p_high.p * 10)} in 10 chance of going above 180 in 2 h.` });
      return {
        pid: p.id,
        name: p.name,
        reasons,
        freshness: { label: st.freshness.label, hours_since_reading: st.freshness.hours_since_reading },
        review: reviews.get(p.id) ?? { status: "unreviewed", note: null, at: null, by: null },
        operational: withOperational(p).operational,
      };
    });
  },
  async doctorReview(pid, body) {
    await wait(200, 400);
    const r: ReviewState = { status: body.status, note: body.note || null, at: fmtLocal(new Date()), by: "DevTester" };
    reviews.set(pid, r);
    return r;
  },
  async doctorBrief(pid) {
    await wait();
    const p = withOperational(patientDetail(pid));
    const model = modelById(pid);
    const w = weekStats(model);
    const dinner = model.meals[3];
    const meal = { name: dinner.name, carbs: dinner.carbs, fibre: dinner.fibre, protein: dinner.protein, fat: dinner.fat, minutes_from_now: 30 };
    const wb = buildForecast(model, "2", { meal });
    const ws = buildForecast(model, "2", { meal, walk: { minutes: 15, afterMealMin: 10 } });
    const dPeak = Math.round(ws.peak.value - wb.peak.value);
    return {
      tar_7d_reference: p.tar_7d_reference,
      operational: p.operational,
      replay_now: fmtLocal(nowOf(pid)),
      patient: p,
      tir_7d: w.tir,
      mean_glucose: w.mean,
      gmi: w.gmi,
      hypo_events_7d: w.hypo,
      hyper_events_7d: w.hyper,
      daily_profile: w.profile,
      top_driver: "Large rice portion at lunch",
      suggestions: [
        "Most time above range follows lunch; discuss portion size of rice.",
        "One overnight low this week (around 3-4 am); review evening routine.",
        `Model simulation: a 15-minute walk after the usual dinner changes the simulated peak by ${dPeak} mg/dL (offline mock).`,
      ],
      generated_at: fmtLocal(NOW),
    };
  },
  // Evaluation results are never faked: offline mode has no reports (the Trust panel says so).
  async reportsList() {
    await wait(100, 200);
    return [];
  },
  async report() {
    await wait(120, 260);
    return null;
  },
  async demoTour() {
    await wait(80, 150);
    return { steps: TOUR };
  },
};

const CANCELLED: Record<Lang, string> = {
  "en-IN": "Okay, I did not change anything.",
  "hi-IN": "ठीक है, मैंने कुछ नहीं बदला।",
  "bn-IN": "ঠিক আছে, আমি কিছু বদলাইনি।",
  "kn-IN": "ಸರಿ, ನಾನು ಏನನ್ನೂ ಬದಲಿಸಿಲ್ಲ.",
};
const LOGGED: Record<Lang, string> = {
  "en-IN": "I have added this reading to your twin.",
  "hi-IN": "मैंने यह रीडिंग आपके ट्विन में जोड़ दी है।",
  "bn-IN": "এই রিডিংটা আপনার টুইনে যোগ করেছি।",
  "kn-IN": "ಈ ರೀಡಿಂಗ್ ಅನ್ನು ನಿಮ್ಮ ಟ್ವಿನ್‌ಗೆ ಸೇರಿಸಿದ್ದೇನೆ.",
};

function withOperational<T extends ReturnType<typeof patientDetail>>(p: T): T {
  const st = buildState(modelById(p.id), "2");
  return {
    ...p,
    tar_7d_reference: { value: p.risk_7d, label_en: "Historical time above 180 (dataset reference CGM, last 7 days)" },
    operational: {
      estimate: st.estimate,
      band: st.band,
      last_reading_age_h: st.last_observation ? st.freshness.hours_since_reading : null,
      p_high_2h: st.forecast.p_high.p,
      data_gap: st.freshness.hours_since_reading >= 8,
    },
  };
}

function mockReceipt(pid: string, fc: import("@/api/types").Forecast): Receipt {
  const st = buildState(modelById(pid), "2");
  const claim = (c: ReceiptClaim) => c;
  const last = st.last_observation;
  return {
    forecast_id: fc.forecast_id,
    persona_id: pid,
    replay_now: fmtLocal(nowOf(pid)),
    generated_at: fmtLocal(new Date()),
    claims: [
      claim({ key: "estimate", label_en: "Glucose estimate now", value: st.estimate, unit: "mg/dL", status: "estimated", source: { kind: "tool", ref: "get_state.estimate" } }),
      claim({ key: "band", label_en: "90% band now", value: `${st.band.lo}–${st.band.hi}`, unit: "mg/dL", status: "estimated", source: { kind: "tool", ref: "get_state.band" } }),
      ...(last ? [claim({ key: "last_reading", label_en: "Last reading the twin saw", value: last.value, unit: "mg/dL", status: "measured", source: { kind: last.kind === "cgm" ? "dataset" : "user", ref: last.t } })] : []),
      claim({ key: "p_high", label_en: "Chance of going above 180 in the next 2 h", value: fc.p_high.p, unit: null, status: "validated", source: { kind: "report", ref: "offline mock: no evaluation report" } }),
      claim({ key: "p_low", label_en: "Chance of going below 70 in the next 2 h", value: fc.p_low.p, unit: null, status: "not_validated", source: { kind: "tool", ref: "forecast.p_low" } }),
      claim({ key: "peak", label_en: "Forecast peak", value: fc.peak.value, unit: "mg/dL", status: "estimated", source: { kind: "tool", ref: "forecast.peak" } }),
      claim({ key: "beyond_120", label_en: "Curve beyond 2 hours", value: null, unit: null, status: "exploratory", source: { kind: "tool", ref: "forecast.traj (120–240 min)" } }),
    ],
    inputs: { ladder: "2", replay_now: fmtLocal(nowOf(pid)), observations_used: fc.provenance?.observations_used ?? null },
    model: { model_version: "offline-mock", note: "Offline mock: no model, no evaluation. Nothing here is a real result." },
    tool_calls: [{ name: "forecast", args: { patient_id: pid }, output: { forecast_id: fc.forecast_id, peak: fc.peak } }],
  };
}
