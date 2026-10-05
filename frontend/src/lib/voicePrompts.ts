import type { Lang, VoiceSample } from "@/api/types";

/**
 * Built-in sample questions, used only when GET /api/demo/voice_samples returns nothing for a
 * language (e.g. before the audio fixtures are recorded). Two per language: one meal question that
 * names a local dish, and one "when should I check next?" question. Prompts are written in each
 * language itself, so they stay the same whatever the UI language is.
 */
export const BUILTIN_PROMPTS: Record<Lang, string[]> = {
  "en-IN": ["What will happen if I eat 2 roti and dal now?", "When should I check next?"],
  "hi-IN": ["अगर मैं अभी 2 रोटी और दाल खाऊँ तो क्या होगा?", "मुझे अगली बार शुगर कब चेक करनी चाहिए?"],
  "bn-IN": ["এখন ভাত আর মাছের ঝোল খেলে কী হবে?", "পরের বার কখন পরীক্ষা করব?"],
  "kn-IN": ["ಈಗ ಎರಡು ಚಪಾತಿ ಮತ್ತು ಬೇಳೆ ಸಾರು ತಿಂದರೆ ಏನಾಗುತ್ತದೆ?", "ಮುಂದೆ ಯಾವಾಗ ಪರೀಕ್ಷಿಸಬೇಕು?"],
};

/** Samples for one language: the backend's recorded ones when present, else the built-in prompts. */
export function samplesFor(lang: Lang, fromBackend: VoiceSample[] | undefined): (VoiceSample & { builtin?: boolean })[] {
  const recorded = (fromBackend ?? []).filter((s) => s.lang === lang && s.prompt);
  if (recorded.length) return recorded;
  return BUILTIN_PROMPTS[lang].map((prompt) => ({ lang, prompt, audio_url: "", builtin: true }));
}
