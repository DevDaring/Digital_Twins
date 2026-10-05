import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import type { Lang } from "@/api/types";
import en from "./locales/en-IN.json";
import { useApp } from "@/store/app";

type Bundle = Record<string, unknown>;

/**
 * English ships in the main bundle (it is also the fallback). Hindi, Bengali and Kannada are
 * loaded on demand as separate chunks, which keeps ~170 kB of translations out of the first load.
 */
const LOADERS: Record<Lang, () => Promise<Bundle>> = {
  "en-IN": async () => en as Bundle,
  "hi-IN": () => import("./locales/hi-IN.json").then((m) => m.default as Bundle),
  "bn-IN": () => import("./locales/bn-IN.json").then((m) => m.default as Bundle),
  "kn-IN": () => import("./locales/kn-IN.json").then((m) => m.default as Bundle),
};

export const LANG_LABELS: Record<Lang, { native: string; english: string; short: string }> = {
  "en-IN": { native: "English", english: "English", short: "EN" },
  "hi-IN": { native: "हिन्दी", english: "Hindi", short: "हि" },
  "bn-IN": { native: "বাংলা", english: "Bengali", short: "বা" },
  "kn-IN": { native: "ಕನ್ನಡ", english: "Kannada", short: "ಕ" },
};

void i18n.use(initReactI18next).init({
  resources: { "en-IN": { translation: en } },
  partialBundledLanguages: true,
  lng: "en-IN",
  fallbackLng: "en-IN",
  interpolation: { escapeValue: false },
  returnNull: false,
});

/** Load a language's strings (once) and switch i18next to it. Falls back to English on failure. */
export async function loadLanguage(lang: Lang): Promise<void> {
  try {
    if (!i18n.hasResourceBundle(lang, "translation")) {
      const bundle = await (LOADERS[lang] ?? LOADERS["en-IN"])();
      i18n.addResourceBundle(lang, "translation", bundle, true, true);
    }
    // Ignore a stale load if the user switched again meanwhile.
    if (useApp.getState().lang === lang) await i18n.changeLanguage(lang);
  } catch {
    await i18n.changeLanguage("en-IN");
  }
}

function applyDocumentLang(lang: Lang) {
  if (typeof document !== "undefined") document.documentElement.lang = lang;
}
applyDocumentLang(useApp.getState().lang);

/** Resolves once the stored language is ready (main.tsx waits for it before the first render). */
export const i18nReady: Promise<void> = loadLanguage(useApp.getState().lang);

useApp.subscribe((s, prev) => {
  if (s.lang !== prev.lang) {
    void loadLanguage(s.lang);
    applyDocumentLang(s.lang);
  }
});

export default i18n;
