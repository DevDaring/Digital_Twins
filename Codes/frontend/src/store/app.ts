import { create } from "zustand";
import type { Highlight, Ladder, Lang, MealInput, MealParse, Safety, Scenario, ToolCall } from "@/api/types";
import { readJSON, writeJSON } from "@/lib/storage";

const KEY = "pratifalan.prefs";
export type ThemePref = "system" | "light" | "dark";

interface Prefs {
  lang: Lang;
  ladder: Ladder;
  patientId: string | null;
  theme: ThemePref;
  onboarded: boolean;
  presentation: boolean;
  /** How the stage shows the next hours: the glass body (default) or the chart. */
  stageView: StageView;
}
export type StageView = "body" | "chart";

/** A meal the user has built in the meal flow; drives the forecast overlay and the what-if studio. */
export interface MealDraft {
  parse: MealParse;
  meal: MealInput;
  photoUrl?: string | null;
}

/** The dinner confirmed on the stage (from the meal flow or a quick pick). */
export interface StageDinner {
  meal: MealInput;
  source: "meal" | "usual";
  title: string;
}
export type ChangeKind = "portion" | "walk" | "swap" | "timing";
/** The one change compared against the dinner ("Two possible futures"). */
export interface StageChange {
  kind: ChangeKind;
  scenario: Scenario;
  /** Localised label, used directly on the chart. */
  label: string;
}

interface AppState extends Prefs {
  highlight: Highlight | null;
  lastToolCalls: ToolCall[];
  mealDraft: MealDraft | null;
  whatIfSeed: { base: MealInput; scenario: Scenario } | null;
  /** toolCalls set = opened from an agent answer: show those calls instead of the forecast's own. */
  whyOpen: { forecastId: string | null; toolCalls?: ToolCall[] } | null;
  addReadingOpen: boolean;
  stageDinner: StageDinner | null;
  stageChange: StageChange | null;
  /** A non-ok safety result: shown above everything else, before any success message. */
  safetyAlert: Safety | null;
  tourActive: boolean;
  tourStep: number;
  setLang: (l: Lang) => void;
  setLadder: (l: Ladder) => void;
  setPatient: (id: string) => void;
  setTheme: (t: ThemePref) => void;
  setOnboarded: (v: boolean) => void;
  setHighlight: (h: Highlight | null) => void;
  setLastToolCalls: (c: ToolCall[]) => void;
  setMealDraft: (d: MealDraft | null) => void;
  seedWhatIf: (s: { base: MealInput; scenario: Scenario } | null) => void;
  openWhy: (forecastId: string | null, toolCalls?: ToolCall[]) => void;
  closeWhy: () => void;
  setAddReadingOpen: (v: boolean) => void;
  setStageDinner: (d: StageDinner | null) => void;
  setStageChange: (c: StageChange | null) => void;
  showSafety: (s: Safety | null) => void;
  setPresentation: (v: boolean) => void;
  setStageView: (v: StageView) => void;
  startTour: () => void;
  setTourStep: (n: number) => void;
  endTour: () => void;
}

const defaults: Prefs = { lang: "en-IN", ladder: "2", patientId: null, theme: "system", onboarded: false, presentation: false, stageView: "body" };
const initial: Prefs = { ...defaults, ...readJSON<Partial<Prefs>>(KEY, {}) };

export const useApp = create<AppState>((set, get) => {
  const persist = (patch: Partial<Prefs>) => {
    set(patch);
    const s = get();
    writeJSON(KEY, { lang: s.lang, ladder: s.ladder, patientId: s.patientId, theme: s.theme, onboarded: s.onboarded, presentation: s.presentation, stageView: s.stageView });
  };
  return {
    ...initial,
    highlight: null,
    lastToolCalls: [],
    mealDraft: null,
    whatIfSeed: null,
    whyOpen: null,
    addReadingOpen: false,
    stageDinner: null,
    stageChange: null,
    safetyAlert: null,
    tourActive: false,
    tourStep: 0,
    setLang: (lang) => persist({ lang }),
    setLadder: (ladder) => persist({ ladder }),
    setPatient: (patientId) => {
      persist({ patientId });
      set({ mealDraft: null, highlight: null, whatIfSeed: null, stageDinner: null, stageChange: null });
    },
    setTheme: (theme) => persist({ theme }),
    setOnboarded: (onboarded) => persist({ onboarded }),
    setHighlight: (highlight) => set({ highlight }),
    setLastToolCalls: (lastToolCalls) => set({ lastToolCalls }),
    setMealDraft: (mealDraft) => set({ mealDraft }),
    seedWhatIf: (whatIfSeed) => set({ whatIfSeed }),
    openWhy: (forecastId, toolCalls) => set({ whyOpen: { forecastId, toolCalls } }),
    closeWhy: () => set({ whyOpen: null }),
    setAddReadingOpen: (addReadingOpen) => set({ addReadingOpen }),
    setStageDinner: (stageDinner) => set({ stageDinner, ...(stageDinner ? {} : { stageChange: null }) }),
    setStageChange: (stageChange) => set({ stageChange }),
    showSafety: (safetyAlert) => set({ safetyAlert }),
    setPresentation: (presentation) => persist({ presentation }),
    setStageView: (stageView) => persist({ stageView }),
    startTour: () => set({ tourActive: true, tourStep: 0 }),
    setTourStep: (tourStep) => set({ tourStep }),
    endTour: () => set({ tourActive: false, tourStep: 0 }),
  };
});
