// A tiny rule-based stand-in for the backend agent, used only in offline mock mode. It calls the
// mock twin "tools" and fills fixed templates, so every number in a reply comes from a tool output.
import type { AgentReply, ChatRequest, Ladder, Lang, PendingAction, ToolCall } from "@/api/types";
import { buildForecast, buildNbp, buildState, fmtLocal, modelById, nowOf } from "./sim";
import { assessReading } from "./safety";

/** Actions proposed in chat, waiting for POST /agent/confirm. Nothing is logged before that. */
export const pendingActions = new Map<string, PendingAction & { pid: string; ladder: Ladder; lang: Lang }>();
let actionSeq = 1;

const READING_WORDS = ["sugar", "glucose", "reading", "शुगर", "रीडिंग", "সুগার", "রিডিং", "ಸಕ್ಕರೆ", "ಶುಗರ್", "ರೀಡಿಂಗ್"];

/** "my sugar is 150" / "शुगर 5.6 mmol" -> a reading the user reports, if any. */
export function reportedReading(text: string): { value: number; unit: "mg/dL" | "mmol/L" } | null {
  if (!READING_WORDS.some((w) => text.toLowerCase().includes(w))) return null;
  const m = /(\d{1,3}(?:[.,]\d)?)\s*(mmol)?/i.exec(text);
  if (!m) return null;
  const value = Number(m[1].replace(",", "."));
  const unit = m[2] || (value < 35 && m[1].includes(".")) ? "mmol/L" : "mg/dL";
  if (unit === "mg/dL" && (value < 20 || value > 600)) return null;
  return { value, unit };
}

const CONFIRM_ASK: Record<Lang, (v: string) => string> = {
  "en-IN": (v) => `Shall I add a reading of ${v} to your twin? Nothing changes until you confirm.`,
  "hi-IN": (v) => `क्या मैं ${v} की रीडिंग आपके ट्विन में जोड़ दूँ? आपके पुष्टि करने तक कुछ नहीं बदलेगा।`,
  "bn-IN": (v) => `${v} রিডিংটা কি আপনার টুইনে যোগ করব? আপনি নিশ্চিত না করা পর্যন্ত কিছু বদলাবে না।`,
  "kn-IN": (v) => `${v} ರೀಡಿಂಗ್ ಅನ್ನು ನಿಮ್ಮ ಟ್ವಿನ್‌ಗೆ ಸೇರಿಸಲೇ? ನೀವು ದೃಢೀಕರಿಸುವವರೆಗೆ ಏನೂ ಬದಲಾಗುವುದಿಲ್ಲ.`,
};

const has = (text: string, words: string[]) => words.some((w) => text.toLowerCase().includes(w));

function clock(iso: string, lang: Lang) {
  const d = new Date(iso);
  const h = d.getHours();
  const m = String(d.getMinutes()).padStart(2, "0");
  const h12 = ((h + 11) % 12) + 1;
  const part: Record<Lang, [string, string, string, string]> = {
    "en-IN": ["am", "am", "pm", "pm"],
    "hi-IN": ["सुबह", "सुबह", "दोपहर", "रात"],
    "bn-IN": ["সকাল", "সকাল", "বিকেল", "রাত"],
    "kn-IN": ["ಬೆಳಿಗ್ಗೆ", "ಬೆಳಿಗ್ಗೆ", "ಮಧ್ಯಾಹ್ನ", "ರಾತ್ರಿ"],
  };
  const idx = h < 5 ? 0 : h < 12 ? 1 : h < 17 ? 2 : 3;
  const p = part[lang][idx];
  return lang === "en-IN" ? `${h12}:${m} ${p}` : `${p} ${h12}:${m}`;
}

const T = {
  emergency: {
    "en-IN": "This may be an emergency. Please contact a doctor now or call 108.",
    "hi-IN": "यह आपातकाल हो सकता है। तुरंत डॉक्टर से संपर्क करें या 108 पर कॉल करें।",
    "bn-IN": "এটা জরুরি অবস্থা হতে পারে। এখনই ডাক্তারের সঙ্গে যোগাযোগ করুন বা 108-এ ফোন করুন।",
    "kn-IN": "ಇದು ತುರ್ತು ಪರಿಸ್ಥಿತಿ ಇರಬಹುದು. ಈಗಲೇ ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಿ ಅಥವಾ 108 ಗೆ ಕರೆ ಮಾಡಿ.",
  },
  dose: {
    "en-IN": "I cannot advise on medicine or insulin doses. Please ask your doctor.",
    "hi-IN": "मैं दवा या इंसुलिन की मात्रा के बारे में सलाह नहीं दे सकता। कृपया अपने डॉक्टर से पूछें।",
    "bn-IN": "ওষুধ বা ইনসুলিনের মাত্রা নিয়ে আমি পরামর্শ দিতে পারি না। দয়া করে আপনার ডাক্তারকে জিজ্ঞেস করুন।",
    "kn-IN": "ಔಷಧ ಅಥವಾ ಇನ್ಸುಲಿನ್ ಪ್ರಮಾಣದ ಬಗ್ಗೆ ನಾನು ಸಲಹೆ ನೀಡಲಾರೆ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ವೈದ್ಯರನ್ನು ಕೇಳಿ.",
  },
  dinner: {
    "en-IN": (peak: number, time: string, n: number) =>
      `After your usual dinner, your sugar may peak near ${peak} around ${time}. Going above 180 happens about ${n} times out of 10.`,
    "hi-IN": (peak: number, time: string, n: number) =>
      `रोज़ जैसे खाने के बाद आपकी शुगर ${time} के आसपास ${peak} तक जा सकती है। 180 से ऊपर जाना 10 में से लगभग ${n} बार होता है।`,
    "bn-IN": (peak: number, time: string, n: number) =>
      `রোজকার রাতের খাবারের পরে ${time} নাগাদ আপনার সুগার ${peak}-এর কাছে উঠতে পারে। 180-র ওপরে যাওয়া 10 বারে প্রায় ${n} বার হয়।`,
    "kn-IN": (peak: number, time: string, n: number) =>
      `ಎಂದಿನ ಊಟದ ನಂತರ ${time} ಸುಮಾರಿಗೆ ನಿಮ್ಮ ಸಕ್ಕರೆ ${peak} ಹತ್ತಿರ ಏರಬಹುದು. 180 ಮೀರುವುದು 10 ರಲ್ಲಿ ಸುಮಾರು ${n} ಬಾರಿ.`,
  },
  nbp: {
    "en-IN": (time: string) => `Check at ${time}. That reading will teach me the most.`,
    "hi-IN": (time: string) => `${time} पर जांच करें। उस रीडिंग से मुझे सबसे ज़्यादा पता चलेगा।`,
    "bn-IN": (time: string) => `${time}-এ মাপুন। ওই রিডিং থেকে আমি সবচেয়ে বেশি শিখব।`,
    "kn-IN": (time: string) => `${time} ಕ್ಕೆ ಪರೀಕ್ಷಿಸಿ. ಆ ಅಳತೆಯಿಂದ ನಾನು ಹೆಚ್ಚು ಕಲಿಯುತ್ತೇನೆ.`,
  },
  walk: {
    "en-IN": (a: number, b: number) => `A 15-minute walk after dinner brings the chance of going above 180 from about ${a} to about ${b} times out of 10.`,
    "hi-IN": (a: number, b: number) => `खाने के बाद 15 मिनट टहलने से 180 से ऊपर जाने की संभावना 10 में से लगभग ${a} से घटकर ${b} बार रह जाती है।`,
    "bn-IN": (a: number, b: number) => `রাতের খাবারের পরে 15 মিনিট হাঁটলে 180-র ওপরে যাওয়ার সম্ভাবনা 10 বারে প্রায় ${a} থেকে কমে ${b} বার হয়।`,
    "kn-IN": (a: number, b: number) => `ಊಟದ ನಂತರ 15 ನಿಮಿಷ ನಡೆದರೆ 180 ಮೀರುವ ಸಾಧ್ಯತೆ 10 ರಲ್ಲಿ ಸುಮಾರು ${a} ರಿಂದ ${b} ಬಾರಿಗೆ ಇಳಿಯುತ್ತದೆ.`,
  },
  now: {
    "en-IN": (e: number, lo: number, hi: number) => `Right now your twin thinks you are near ${e}, most likely between ${lo} and ${hi}.`,
    "hi-IN": (e: number, lo: number, hi: number) => `अभी आपकी शुगर लगभग ${e} है, ज़्यादातर ${lo} और ${hi} के बीच।`,
    "bn-IN": (e: number, lo: number, hi: number) => `এখন আপনার সুগার প্রায় ${e}, সম্ভবত ${lo} থেকে ${hi}-এর মধ্যে।`,
    "kn-IN": (e: number, lo: number, hi: number) => `ಈಗ ನಿಮ್ಮ ಸಕ್ಕರೆ ಸುಮಾರು ${e}, ಹೆಚ್ಚಾಗಿ ${lo} ಮತ್ತು ${hi} ನಡುವೆ.`,
  },
};

export function mockChat(req: ChatRequest): AgentReply {
  const model = modelById(req.patient_id);
  const lang = req.lang;
  const text = req.text;
  const tool_calls: ToolCall[] = [];
  const base = {
    lang,
    tool_calls,
    grounding: { passed: true, numbers: [] as string[], fallback_used: false },
    safety: { blocked: false, emergency: false, reason: null as string | null },
    audio_url: null,
    source: "fixture" as const,
  };

  if (has(text, ["faint", "unconscious", "chest pain", "बेहोश", "चक्कर", "অজ্ঞান", "মাথা ঘুর", "ಪ್ರಜ್ಞೆ", "ತಲೆ ಸುತ್ತ"])) {
    return { ...base, reply: T.emergency[lang], intent: "emergency", safety: { blocked: true, emergency: true, reason: "symptom_keywords" }, highlight: { view: "none" } };
  }
  const rr = reportedReading(text);
  if (rr) {
    const mgdl = rr.unit === "mmol/L" ? rr.value * 18.016 : rr.value;
    const safety = assessReading(mgdl, lang);
    const id = `mock-act-${actionSeq++}`;
    const shown = `${rr.value} ${rr.unit}`;
    const action: PendingAction = { id, kind: "log_reading", summary_en: `Log a reading of ${shown}`, payload: { value: rr.value, unit: rr.unit } };
    pendingActions.set(id, { ...action, pid: req.patient_id, ladder: req.ladder, lang });
    const urgent = safety.level !== "ok";
    return {
      ...base,
      // Safety messages are shown immediately; the reading itself waits for confirmation.
      reply: urgent ? `${safety.title}. ${safety.message} ${CONFIRM_ASK[lang](shown)}` : CONFIRM_ASK[lang](shown),
      intent: "log_reading",
      safety: { blocked: false, emergency: safety.emergency, reason: urgent ? `${safety.level}_reading` : null },
      highlight: { view: "none" },
      claims: [{ slot: "reading", field: "user.text", value: rr.value, rendered: shown }],
      pending_action: action,
    };
  }
  if (has(text, ["insulin", "dose", "medicine", "tablet", "इंसुलिन", "दवा", "डोज़", "ওষুধ", "ইনসুলিন", "ಔಷಧ", "ಇನ್ಸುಲಿನ್", "ಮಾತ್ರೆ"])) {
    return { ...base, reply: T.dose[lang], intent: "out_of_scope", safety: { blocked: true, emergency: false, reason: "dose_request" }, highlight: { view: "none" } };
  }
  if (has(text, ["walk", "टहल", "हाँट", "হাঁট", "ನಡೆ", "ನಡಿ", "roti", "रोटी"])) {
    const meal = { name: "Usual dinner", carbs: model.meals[3].carbs, fibre: model.meals[3].fibre, protein: model.meals[3].protein, fat: model.meals[3].fat, minutes_from_now: 50 };
    const b = buildForecast(model, req.ladder, { meal });
    const s = buildForecast(model, req.ladder, { meal, walk: { minutes: 15, afterMealMin: 10 } });
    const a = Math.round(b.p_high.p * 10);
    const c = Math.round(s.p_high.p * 10);
    tool_calls.push({ name: "what_if", args: { base_meal: meal, scenario: { walk_min: 15, walk_after_min: 10 } }, output: { baseline_p_high: b.p_high, scenario_p_high: s.p_high } });
    return {
      ...base,
      reply: T.walk[lang](a, c),
      intent: "what_if",
      grounding: { passed: true, numbers: ["15", "180", String(a), String(c)], fallback_used: false },
      highlight: { view: "whatif" },
    };
  }
  if (has(text, ["when", "next", "check", "कब", "জांच", "কখন", "মাপ", "ಯಾವಾಗ", "ಪರೀಕ್ಷ"])) {
    const nbp = buildNbp(model, req.ladder);
    tool_calls.push({ name: "next_best_prick", args: { patient_id: req.patient_id }, output: nbp });
    const time = clock(nbp.time, lang);
    return { ...base, reply: T.nbp[lang](time), intent: "next_best_prick", grounding: { passed: true, numbers: [time], fallback_used: false }, highlight: { view: "nbp", from: nbp.time } };
  }
  if (has(text, ["now", "right now", "अभी", "এখন", "ಈಗ"])) {
    const st = buildState(model, req.ladder);
    tool_calls.push({ name: "get_state", args: { patient_id: req.patient_id, at: st.now }, output: { estimate: st.estimate, band: st.band, freshness: st.freshness } });
    const from = new Date(nowOf(req.patient_id));
    from.setHours(from.getHours() - 3);
    return {
      ...base,
      reply: T.now[lang](st.estimate, st.band.lo, st.band.hi),
      intent: "state",
      grounding: { passed: true, numbers: [st.estimate, st.band.lo, st.band.hi].map(String), fallback_used: false },
      highlight: { view: "stage", from: fmtLocal(from), to: st.now },
    };
  }
  // Default: dinner forecast.
  const dinner = model.meals[3];
  const meal = { name: dinner.name, carbs: dinner.carbs, fibre: dinner.fibre, protein: dinner.protein, fat: dinner.fat, minutes_from_now: 50 };
  const fc = buildForecast(model, req.ladder, { meal });
  tool_calls.push({ name: "forecast", args: { patient_id: req.patient_id, horizon_min: 240, meal }, output: { peak: fc.peak, p_high: fc.p_high, p_low: fc.p_low } });
  const n = Math.round(fc.p_high.p * 10);
  const NOW = nowOf(req.patient_id);
  const end = new Date(NOW);
  end.setMinutes(end.getMinutes() + 210);
  return {
    ...base,
    reply: T.dinner[lang](fc.peak.value, clock(fc.peak.t, lang), n),
    intent: "forecast",
    grounding: { passed: true, numbers: [String(fc.peak.value), "180", String(n)], fallback_used: false },
    highlight: { view: "forecast", from: fmtLocal(NOW), to: fmtLocal(end) },
  };
}
