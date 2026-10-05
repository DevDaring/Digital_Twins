import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AnimatePresence, m as motion, useReducedMotion } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { AlertOctagon, AlertTriangle, Check, CheckCircle2, Circle, ClipboardCheck, Droplet, HelpCircle, Loader2, Mic, Phone, Send, ShieldAlert, ShieldOff, Sparkles, Square, Volume2, X } from "lucide-react";
import { api } from "@/api";
import { ApiError, mediaUrl } from "@/api/http";
import type { AgentReply, Lang, PendingAction, Safety, ToolCall } from "@/api/types";
import { isUrgent } from "@/lib/evidence";
import { samplesFor } from "@/lib/voicePrompts";
import { LANGS } from "@/api/types";
import { useActivePatientId, useHealth, useTwinState, useVoiceSamples } from "@/api/hooks";
import { GlucoseRiver } from "@/charts/GlucoseRiver";
import { LANG_LABELS } from "@/i18n";
import { replySource } from "@/lib/replySource";
import { formatClock } from "@/lib/format";
import { useApp } from "@/store/app";

type Phase = "idle" | "listening" | "transcribing" | "review" | "thinking" | "voicing" | "speaking";
type StepState = "todo" | "active" | "done" | "skipped";
interface Turn {
  id: number;
  who: "you" | "twin";
  text: string;
  lang: Lang;
  reply?: AgentReply;
  via?: "browser";
}

/* ---- Web Speech API typing (not in lib.dom for all browsers) ---- */
interface SRAlternative {
  transcript: string;
}
interface SRResult {
  isFinal: boolean;
  0: SRAlternative;
}
interface SREvent {
  resultIndex: number;
  results: ArrayLike<SRResult>;
}
interface SpeechRec {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: SREvent) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}
function getSR(): (new () => SpeechRec) | null {
  const w = window as unknown as { SpeechRecognition?: new () => SpeechRec; webkitSpeechRecognition?: new () => SpeechRec };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

function speakWithBrowser(text: string, lang: Lang): Promise<void> {
  return new Promise((resolve) => {
    if (!("speechSynthesis" in window)) return resolve();
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang;
    const voices = window.speechSynthesis.getVoices();
    const v = voices.find((x) => x.lang === lang) ?? voices.find((x) => x.lang.startsWith(lang.slice(0, 2)));
    if (v) u.voice = v;
    u.rate = 0.95;
    u.onend = () => resolve();
    u.onerror = () => resolve();
    window.speechSynthesis.speak(u);
  });
}

/* ---------------- Orb + waveform ---------------- */
function Orb({ phase, analyser, onDown, onUp, label }: { phase: Phase; analyser: AnalyserNode | null; onDown: () => void; onUp: () => void; label: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const S = 300;
    c.width = S * dpr;
    c.height = S * dpr;
    ctx.scale(dpr, dpr);
    const data = new Uint8Array(analyser ? analyser.frequencyBinCount : 64);
    let raf = 0;
    let tick = 0;
    const N = 72;
    const draw = () => {
      tick += 1;
      ctx.clearRect(0, 0, S, S);
      if (analyser) analyser.getByteFrequencyData(data);
      const cx = S / 2;
      const r0 = 88;
      for (let i = 0; i < N; i++) {
        const a = (i / N) * Math.PI * 2 - Math.PI / 2;
        let amp: number;
        if (analyser && phase === "listening") {
          const bin = data[Math.floor((i % (N / 2)) * (data.length / (N / 2)) * 0.6)] / 255;
          amp = 4 + bin * 46;
        } else if (phase === "speaking" || phase === "thinking" || phase === "transcribing" || phase === "voicing") {
          const slow = phase !== "speaking";
          amp = reduce ? 6 : 6 + (Math.sin(tick / (slow ? 14 : 6) + i * 0.5) + 1) * (slow ? 4 : 10);
        } else {
          amp = reduce ? 3 : 3 + (Math.sin(tick / 40 + i * 0.35) + 1) * 2;
        }
        const x0 = cx + Math.cos(a) * r0;
        const y0 = cx + Math.sin(a) * r0;
        const x1 = cx + Math.cos(a) * (r0 + amp);
        const y1 = cx + Math.sin(a) * (r0 + amp);
        ctx.strokeStyle = phase === "listening" ? "rgba(242,163,58,0.9)" : "rgba(237,235,255,0.42)";
        ctx.lineWidth = 3;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.stroke();
      }
      if (!reduce || phase === "listening") raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, [analyser, phase, reduce]);

  return (
    <div className="relative mx-auto h-[300px] w-[300px]">
      <canvas ref={canvas} className="absolute inset-0 h-full w-full" aria-hidden />
      <div className="absolute inset-0 flex items-center justify-center">
      <motion.button
        type="button"
        aria-label={label}
        aria-pressed={phase === "listening"}
        onPointerDown={(e) => {
          e.preventDefault();
          onDown();
        }}
        onPointerUp={onUp}
        onPointerCancel={onUp}
        onKeyDown={(e) => {
          if ((e.key === " " || e.key === "Enter") && !e.repeat) {
            e.preventDefault();
            onDown();
          }
        }}
        onKeyUp={(e) => {
          if (e.key === " " || e.key === "Enter") {
            e.preventDefault();
            onUp();
          }
        }}
        animate={phase === "listening" ? { scale: 1.06 } : { scale: 1 }}
        transition={{ type: "spring", damping: 18, stiffness: 260 }}
        className={`flex h-[150px] w-[150px] touch-none select-none items-center justify-center rounded-full ${
          phase === "listening" ? "bg-marigold text-night shadow-glow" : "bg-gradient-to-b from-night-3 to-night-2 text-moon ring-1 ring-night-line"
        }`}
        data-tour="voice-orb"
      >
        {phase === "listening" ? <Square size={36} aria-hidden /> : phase === "speaking" ? <Volume2 size={40} aria-hidden /> : <Mic size={44} aria-hidden />}
      </motion.button>
      </div>
    </div>
  );
}

/* ---------------- progress: speech-to-text, twin tools, voice ---------------- */
function Progress({ stt, tools, voice, onCancel }: { stt: StepState; tools: StepState; voice: StepState; onCancel?: () => void }) {
  const { t } = useTranslation();
  const steps: { k: string; s: StepState; label: string }[] = [
    { k: "stt", s: stt, label: t("voice.step.stt") },
    { k: "tools", s: tools, label: t("voice.step.tools") },
    { k: "voice", s: voice, label: t("voice.step.voice") },
  ];
  return (
    <div className="mt-3 flex flex-wrap items-center justify-center gap-2" role="status" aria-live="polite">
      <ol className="flex flex-wrap items-center gap-1.5">
        {steps.map((st) => (
          <li
            key={st.k}
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${
              st.s === "active" ? "border-marigold bg-marigold/15 text-marigold" : st.s === "done" ? "border-teal/60 text-teal" : st.s === "skipped" ? "border-night-line text-moon-3 line-through" : "border-night-line text-moon-3"
            }`}
          >
            {st.s === "active" ? <Loader2 size={12} className="animate-spin" aria-hidden /> : st.s === "done" ? <Check size={12} aria-hidden /> : <Circle size={10} aria-hidden />}
            {st.label}
            <span className="sr-only">: {t(`voice.stepState.${st.s}`)}</span>
          </li>
        ))}
      </ol>
      {onCancel && (
        <button type="button" onClick={onCancel} className="inline-flex items-center gap-1 rounded-full border border-coral-night/60 px-3 py-1 text-xs font-bold text-coral-night hover:bg-coral/10">
          <X size={12} aria-hidden />
          {t("common.cancel")}
        </button>
      )}
    </div>
  );
}

/** "Log a reading of 150 mg/dL?" card: nothing changes until the user confirms (contract C8). */
function ConfirmCard({ action, busy, done, onConfirm }: { action: PendingAction; busy: boolean; done: "confirmed" | "cancelled" | null; onConfirm: (ok: boolean) => void }) {
  const { t, i18n } = useTranslation();
  const p = action.payload ?? {};
  const value = typeof p.value === "number" || typeof p.value === "string" ? String(p.value) : null;
  const unit = typeof p.unit === "string" ? p.unit : "mg/dL";
  const summary =
    action.kind === "log_reading" && value
      ? t("voice.confirmReading", { value, unit })
      : action.kind === "log_meal"
        ? t("voice.confirmMeal", { name: String(p.name ?? p.meal ?? ""), carbs: p.carbs !== undefined ? String(p.carbs) : "?" })
        : i18n.language === "en-IN"
          ? action.summary_en
          : t("voice.confirmGeneric");
  return (
    <div className="mt-3 rounded-2xl border border-marigold/60 bg-night/60 p-3" role="group" aria-label={t("voice.confirmTitle")}>
      <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-marigold">
        <ClipboardCheck size={13} aria-hidden />
        {t("voice.confirmTitle")}
      </p>
      <p className="mt-1 text-base font-semibold text-moon">{summary}</p>
      <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 text-xs text-moon-2">
        {Object.entries(p)
          .filter(([, v]) => v !== null && v !== undefined && typeof v !== "object")
          .map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="font-mono text-moon-3" lang="en">{k}</dt>
              <dd className="num">{String(v)}</dd>
            </div>
          ))}
      </dl>
      {done ? (
        <p className="mt-2 text-sm font-semibold text-moon-2">{done === "confirmed" ? t("voice.confirmed") : t("voice.cancelledAction")}</p>
      ) : (
        <div className="mt-3 flex gap-2">
          <button type="button" className="btn-marigold h-10 min-h-0 flex-1 text-sm" disabled={busy} onClick={() => onConfirm(true)}>
            {busy ? <Loader2 size={15} className="animate-spin" aria-hidden /> : <Check size={15} aria-hidden />}
            {t("voice.confirmYes")}
          </button>
          <button type="button" className="btn-night h-10 min-h-0 flex-1 text-sm" disabled={busy} onClick={() => onConfirm(false)}>
            {t("voice.confirmNo")}
          </button>
        </div>
      )}
    </div>
  );
}

/** A non-ok safety result carried in a reply's tool outputs (logged reading). */
function safetyOf(reply: AgentReply): Safety | null {
  for (const c of reply.tool_calls ?? []) {
    const o = c.output as { safety?: Safety } | null;
    if (o && typeof o === "object" && o.safety && typeof o.safety === "object" && "level" in o.safety) return o.safety;
  }
  return null;
}

/* ---------------- page ---------------- */
export default function VoicePage() {
  const { t, i18n } = useTranslation();
  const appLang = useApp((s) => s.lang);
  const ladder = useApp((s) => s.ladder);
  const highlight = useApp((s) => s.highlight);
  const setHighlight = useApp((s) => s.setHighlight);
  const setToolCalls = useApp((s) => s.setLastToolCalls);
  /** The forecast an answer is about (tool output), else the twin's current forecast. */
  const forecastIdOf = (calls: ToolCall[] | undefined) => {
    for (const c of calls ?? []) {
      const o = c.output as { forecast_id?: unknown } | null;
      if (o && typeof o === "object" && typeof o.forecast_id === "string") return o.forecast_id;
    }
    return null;
  };
  const openWhy = useApp((s) => s.openWhy);
  const pid = useActivePatientId();
  const pidNow = useRef(pid);
  pidNow.current = pid;
  const state = useTwinState(pid, ladder);
  const samples = useVoiceSamples();
  // In demo mode the backend has no server voice (POST /speech/tts answers 404), so go straight to the browser voice.
  const health = useHealth();

  const [lang, setLang] = useState<Lang>(appLang);
  useEffect(() => setLang(appLang), [appLang]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [interim, setInterim] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);
  const [draft, setDraft] = useState<{ text: string; via?: "browser" } | null>(null);
  const [steps, setSteps] = useState<{ stt: StepState; tools: StepState; voice: StepState } | null>(null);
  const [confirmBusy, setConfirmBusy] = useState<string | null>(null);
  const [actionDone, setActionDone] = useState<Record<string, "confirmed" | "cancelled">>({});
  const abortRef = useRef<AbortController | null>(null);
  const runId = useRef(0);
  const qc = useQueryClient();
  const showSafety = useApp((st) => st.showSafety);

  const rec = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const stream = useRef<MediaStream | null>(null);
  const actx = useRef<AudioContext | null>(null);
  const sr = useRef<SpeechRec | null>(null);
  const srFinal = useRef("");
  const srEnded = useRef<Promise<void> | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const downAt = useRef(0);
  const active = useRef(false);
  const starting = useRef<Promise<void> | null>(null);
  const seq = useRef(0);
  const listRef = useRef<HTMLDivElement>(null);

  const push = (turn: Omit<Turn, "id">) => setTurns((ts) => [...ts, { ...turn, id: ++seq.current }]);

  useEffect(() => {
    listRef.current?.lastElementChild?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [turns]);

  const stopAudio = useCallback(() => {
    audio.current?.pause();
    audio.current = null;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }, []);

  useEffect(
    () => () => {
      stopAudio();
      stream.current?.getTracks().forEach((tr) => tr.stop());
      void actx.current?.close().catch(() => undefined);
      sr.current?.abort();
    },
    [stopAudio],
  );

  const play = async (src: string): Promise<boolean> => {
    try {
      const el = new Audio(src);
      audio.current = el;
      await new Promise<void>((resolve, reject) => {
        el.onended = () => resolve();
        el.onerror = () => reject(new Error("audio"));
        el.play().catch(reject);
      });
      return true;
    } catch {
      return false;
    }
  };

  const speak = async (reply: AgentReply, run = runId.current) => {
    setSteps((st) => (st ? { ...st, voice: "active" } : st));
    let ok = false;
    const url = mediaUrl(reply.audio_url);
    if (url) {
      setPhase("speaking");
      ok = await play(url);
    }
    if (!ok && health.data?.mode !== "demo") {
      setPhase("voicing");
      try {
        const blob = await api.tts(reply.reply, reply.lang);
        if (run !== runId.current) return;
        if (blob && blob.size > 0) {
          const u = URL.createObjectURL(blob);
          setPhase("speaking");
          ok = await play(u);
          URL.revokeObjectURL(u);
        }
      } catch {
        ok = false;
      }
    }
    if (run !== runId.current) return;
    setPhase("speaking");
    if (!ok) await speakWithBrowser(reply.reply, reply.lang);
    if (run !== runId.current) return;
    setSteps((st) => (st ? { ...st, voice: "done" } : st));
    setPhase((p) => (p === "speaking" ? "idle" : p));
  };

  /** Stop whatever is running: transcription, the agent call or the voice. */
  const cancel = () => {
    runId.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    stopAudio();
    setSteps(null);
    setPhase("idle");
  };

  const ask = async (text: string, via?: "browser", sttDone = false) => {
    const q = text.trim();
    if (!q || !pid) return;
    const run = ++runId.current;
    const askedFor = pid;
    push({ who: "you", text: q, lang, via });
    setDraft(null);
    setPhase("thinking");
    setSteps({ stt: sttDone ? "done" : "skipped", tools: "active", voice: "todo" });
    setNotice(null);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const reply = await api.agentChat({ patient_id: pid, text: q, lang, ladder }, ctrl.signal);
      if (run !== runId.current || askedFor !== pidNow.current) return; // cancelled or persona switched
      push({ who: "twin", text: reply.reply, lang: reply.lang ?? lang, reply });
      setToolCalls(reply.tool_calls ?? []);
      setHighlight(reply.highlight?.view && reply.highlight.view !== "none" ? reply.highlight : null);
      setSteps((st) => (st ? { ...st, tools: "done" } : st));
      await speak(reply, run);
    } catch (e) {
      if (run !== runId.current || (e as Error).name === "AbortError") return;
      setNotice(e instanceof ApiError && e.status === 429 ? t("errors.rateLimited", { s: e.retryAfter ?? 30 }) : t("voice.error"));
      setSteps(null);
      setPhase("idle");
    } finally {
      if (abortRef.current === ctrl) abortRef.current = null;
    }
  };

  const confirmAction = async (action: PendingAction, ok: boolean) => {
    if (confirmBusy) return;
    setConfirmBusy(action.id);
    try {
      const reply = await api.agentConfirm({ action_id: action.id, confirm: ok, lang });
      setActionDone((d) => ({ ...d, [action.id]: ok ? "confirmed" : "cancelled" }));
      push({ who: "twin", text: reply.reply, lang: reply.lang ?? lang, reply });
      if (ok) {
        const sft = safetyOf(reply);
        if (sft && isUrgent(sft.level)) showSafety(sft);
        void qc.invalidateQueries();
      }
    } catch {
      setNotice(t("voice.error"));
    } finally {
      setConfirmBusy(null);
    }
  };

  const start = async () => {
    stopAudio();
    setNotice(null);
    setInterim("");
    srFinal.current = "";
    chunks.current = [];
    const SR = getSR();
    let gotMic = false;
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = s;
      gotMic = true;
      const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (Ctx) {
        const ctx = new Ctx();
        const src = ctx.createMediaStreamSource(s);
        const an = ctx.createAnalyser();
        an.fftSize = 256;
        an.smoothingTimeConstant = 0.75;
        src.connect(an);
        actx.current = ctx;
        setAnalyser(an);
      }
      if (typeof MediaRecorder !== "undefined") {
        const mr = new MediaRecorder(s);
        mr.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
        mr.start();
        rec.current = mr;
      }
    } catch {
      if (!SR) {
        setNotice(t("voice.micDenied"));
        active.current = false;
        return;
      }
    }
    if (!gotMic && !SR) {
      setNotice(t("voice.unsupported"));
      active.current = false;
      return;
    }
    // Run browser recognition in parallel: live transcript now, fallback text later.
    if (SR) {
      try {
        const r = new SR();
        r.lang = lang;
        r.continuous = true;
        r.interimResults = true;
        r.onresult = (e) => {
          let fin = "";
          let mid = "";
          for (let i = 0; i < e.results.length; i++) {
            const res = e.results[i];
            if (res.isFinal) fin += res[0].transcript;
            else mid += res[0].transcript;
          }
          srFinal.current = fin;
          setInterim((fin + " " + mid).trim());
        };
        srEnded.current = new Promise((resolve) => {
          r.onend = () => resolve();
          r.onerror = () => resolve();
        });
        r.start();
        sr.current = r;
      } catch {
        sr.current = null;
      }
    }
    setPhase("listening");
  };

  const stop = async () => {
    if (!active.current) return;
    active.current = false;
    await starting.current;
    setPhase("thinking");
    const mr = rec.current;
    const blob = await new Promise<Blob | null>((resolve) => {
      if (!mr || mr.state === "inactive") return resolve(null);
      mr.onstop = () => resolve(chunks.current.length ? new Blob(chunks.current, { type: mr.mimeType || "audio/webm" }) : null);
      mr.stop();
    });
    rec.current = null;
    stream.current?.getTracks().forEach((tr) => tr.stop());
    stream.current = null;
    void actx.current?.close().catch(() => undefined);
    actx.current = null;
    setAnalyser(null);
    if (sr.current) {
      sr.current.stop();
      await Promise.race([srEnded.current, new Promise((r) => setTimeout(r, 900))]);
      sr.current = null;
    }

    let text = "";
    let via: "browser" | undefined;
    const run = ++runId.current;
    setPhase("transcribing");
    setSteps({ stt: "active", tools: "todo", voice: "todo" });
    if (blob && blob.size > 0) {
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      try {
        text = (await api.stt(blob, lang, ctrl.signal)).text?.trim() ?? "";
      } catch {
        text = "";
      }
      if (abortRef.current === ctrl) abortRef.current = null;
    }
    if (run !== runId.current) return; // cancelled
    if (!text) {
      text = (srFinal.current || interim).trim();
      if (text) via = "browser";
    }
    setInterim("");
    if (!text) {
      setNotice(getSR() ? t("voice.noSpeech") : t("voice.unsupported"));
      setSteps(null);
      setPhase("idle");
      return;
    }
    // Speak -> Confirm -> Act: show the editable transcript; nothing is sent until the user does.
    setSteps({ stt: "done", tools: "todo", voice: "todo" });
    setDraft({ text, via });
    setPhase("review");
  };

  // Push-to-talk: hold to talk; a short tap toggles (easier on phones and for keyboard users).
  const onDown = () => {
    if (active.current) {
      void stop();
      return;
    }
    if (phase === "thinking" || phase === "transcribing") return;
    setDraft(null);
    active.current = true;
    downAt.current = Date.now();
    starting.current = start();
  };
  const onUp = () => {
    if (!active.current) return;
    if (Date.now() - downAt.current >= 350) void stop();
  };

  const submitTyped = (e: FormEvent) => {
    e.preventDefault();
    const q = typed;
    setTyped("");
    void ask(q);
  };

  const langSamples = samplesFor(lang, samples.data);
  const lastTwin = [...turns].reverse().find((x) => x.who === "twin")?.reply;
  const hl = highlight;
  const s = state.data;
  const phaseLabel =
    phase === "listening"
      ? t("voice.listening")
      : phase === "transcribing"
        ? t("voice.transcribing")
        : phase === "review"
          ? t("voice.reviewHint")
          : phase === "thinking"
            ? t("voice.thinking")
            : phase === "voicing"
              ? t("voice.voicing")
              : phase === "speaking"
                ? t("voice.speaking")
                : t("voice.hold");
  const busy = phase === "transcribing" || phase === "thinking" || phase === "voicing" || phase === "speaking";

  return (
    <div className="stage on-night min-h-[calc(100dvh-4rem)]">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 pb-10 pt-6 sm:px-6 lg:grid-cols-[1fr_1.05fr]">
        {/* ---------------- left: orb ---------------- */}
        <section aria-labelledby="voice-title" className="flex flex-col items-center text-center">
          <h1 id="voice-title" className="text-2xl font-extrabold text-moon sm:text-3xl">
            {t("voice.title")}
          </h1>
          <p className="mt-1 max-w-md text-moon-2">{t("voice.subtitle")}</p>

          <div role="radiogroup" aria-label={t("voice.answerLang")} className="mt-5 flex flex-wrap justify-center gap-2">
            {LANGS.map((l) => (
              <button
                key={l}
                type="button"
                role="radio"
                aria-checked={lang === l}
                lang={l}
                onClick={() => setLang(l)}
                className={`chip min-h-[40px] px-4 ${lang === l ? "border-marigold bg-marigold text-night" : "border-night-line text-moon-2 hover:text-moon"}`}
              >
                {LANG_LABELS[l].native}
              </button>
            ))}
          </div>

          <div className="mt-4">
            <Orb phase={phase} analyser={analyser} onDown={onDown} onUp={onUp} label={phase === "listening" ? t("voice.release") : t("voice.hold")} />
          </div>
          <p className="-mt-2 text-sm font-semibold text-moon-2" role="status" aria-live="polite">
            {phaseLabel}
          </p>
          {steps && phase !== "review" && <Progress stt={steps.stt} tools={steps.tools} voice={steps.voice} onCancel={busy ? cancel : undefined} />}
          {draft && phase === "review" && (
            <form
              className="mt-4 w-full max-w-lg rounded-3xl border border-marigold/50 bg-night-2 p-4 text-left"
              onSubmit={(e) => {
                e.preventDefault();
                void ask(draft.text, draft.via, true);
              }}
            >
              <label htmlFor="transcript" className="text-xs font-bold uppercase tracking-wide text-marigold">
                {t("voice.transcriptLabel")}
              </label>
              <textarea
                id="transcript"
                lang={lang}
                rows={2}
                value={draft.text}
                onChange={(e) => setDraft({ ...draft, text: e.target.value })}
                className="mt-1.5 w-full resize-none rounded-2xl border border-night-line bg-night px-3 py-2 text-lg text-moon focus:border-marigold focus:outline-none focus:ring-2 focus:ring-marigold/40"
              />
              <p className="mt-1 text-xs text-moon-3">{draft.via === "browser" ? t("voice.browserStt") : t("voice.transcriptHint")}</p>
              <div className="mt-3 flex gap-2">
                <button type="submit" className="btn-marigold h-11 min-h-0 flex-1" disabled={!draft.text.trim()}>
                  <Send size={16} aria-hidden />
                  {t("voice.sendTranscript")}
                </button>
                <button
                  type="button"
                  className="btn-night h-11 min-h-0"
                  onClick={() => {
                    setDraft(null);
                    setSteps(null);
                    setPhase("idle");
                  }}
                >
                  {t("common.cancel")}
                </button>
              </div>
            </form>
          )}
          <AnimatePresence>
            {interim && (
              <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} lang={lang} className="mt-3 max-w-md text-xl font-medium text-moon">
                “{interim}”
              </motion.p>
            )}
          </AnimatePresence>
          {notice && (
            <p role="alert" className="mt-3 max-w-md rounded-2xl bg-night-2 px-4 py-2.5 text-sm text-moon">
              {notice}
            </p>
          )}

          <div className="mt-6 w-full max-w-lg">
            <p className="eyebrow mb-2 text-moon-3">{t("voice.samples")}</p>
            <div className="flex flex-wrap justify-center gap-2">
              {samples.isLoading && <span className="skeleton-night h-10 w-60" />}
              {!samples.isLoading && langSamples.map((sm, i) => (
                <button
                  key={`${sm.lang}-${i}`}
                  type="button"
                  lang={sm.lang}
                  disabled={busy || phase === "listening"}
                  onClick={async () => {
                    if (sm.lang !== lang) setLang(sm.lang);
                    const url = mediaUrl(sm.audio_url);
                    if (url) await play(url);
                    void ask(sm.prompt);
                  }}
                  className="chip min-h-[44px] border-night-line bg-night-2/70 text-left text-moon hover:border-marigold/60 disabled:opacity-50"
                >
                  <Sparkles size={14} className="shrink-0 text-marigold" aria-hidden />
                  {sm.prompt}
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={submitTyped} className="mt-6 flex w-full max-w-lg gap-2">
            <label htmlFor="typed" className="sr-only">
              {t("voice.typeLabel")}
            </label>
            <input
              id="typed"
              lang={lang}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder={t("voice.typePlaceholder")}
              className="min-h-[48px] flex-1 rounded-full border border-night-line bg-night-2 px-5 text-moon placeholder:text-moon-3 focus:border-marigold focus:outline-none focus:ring-2 focus:ring-marigold/40"
            />
            <button type="submit" className="btn-marigold h-12 w-12 p-0" aria-label={t("voice.send")} disabled={!typed.trim() || busy}>
              <Send size={18} aria-hidden />
            </button>
          </form>
        </section>

        {/* ---------------- right: conversation + chart ---------------- */}
        <section aria-label={t("voice.twin")} className="flex min-w-0 flex-col gap-4">
          <div className="stage-card p-3 sm:p-4">
            {s ? (
              <GlucoseRiver state={s} rangeHours={6} compact highlight={hl && (hl.view === "stage" || hl.view === "forecast") ? hl : null} />
            ) : (
              <div className="skeleton-night h-[210px]" />
            )}
            <AnimatePresence>
              {lastTwin && lastTwin.highlight?.view !== "none" && (
                <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-2 flex flex-wrap items-center gap-2 px-1 text-sm">
                  {(lastTwin.highlight.view === "stage" || lastTwin.highlight.view === "forecast") && lastTwin.highlight.from && <span className="text-marigold">{t("voice.showOnChart")}</span>}
                  {lastTwin.highlight.view === "whatif" && (
                    <Link to="/whatif" className="btn-night h-10 min-h-0">
                      <Sparkles size={15} aria-hidden />
                      {t("voice.openWhatIf")}
                    </Link>
                  )}
                  {lastTwin.highlight.view === "nbp" && s && (
                    <Link to="/" className="inline-flex items-center gap-2 rounded-2xl bg-marigold/15 px-3 py-2 font-semibold text-marigold ring-1 ring-marigold/60">
                      <Droplet size={15} aria-hidden />
                      {t("nbp.headline", { time: formatClock(s.next_best_prick.time, i18n.language) })}
                    </Link>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <div ref={listRef} className="flex flex-col gap-3" aria-live="polite">
            {turns.length === 0 && <p className="stage-card p-5 text-moon-2">{t("voice.empty")}</p>}
            {turns.map((tu) =>
              tu.who === "you" ? (
                <motion.div key={tu.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="ml-auto max-w-[85%] rounded-3xl rounded-br-lg bg-moon px-4 py-3 text-night">
                  <p className="text-xs font-semibold text-night/60">
                    {t("voice.you")}
                    {tu.via === "browser" && <span className="ml-2 font-normal">· {t("voice.browserStt")}</span>}
                  </p>
                  <p lang={tu.lang} className="text-[1.05rem]">
                    {tu.text}
                  </p>
                </motion.div>
              ) : (
                <motion.div
                  key={tu.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`max-w-[92%] rounded-3xl rounded-bl-lg px-4 py-3 ${tu.reply?.safety.emergency ? "bg-[rgb(176_56_40)] text-white" : "border border-night-line bg-night-2 text-moon"}`}
                >
                  <p className={`flex items-center gap-2 text-xs font-semibold ${tu.reply?.safety.emergency ? "text-white" : "text-marigold"}`}>
                    {tu.reply?.safety.emergency ? <AlertOctagon size={14} aria-hidden /> : null}
                    {tu.reply?.safety.emergency ? t("voice.emergency") : t("voice.twin")}
                  </p>
                  <p lang={tu.lang} className="mt-0.5 text-[1.08rem] leading-relaxed">
                    {tu.text}
                  </p>
                  {tu.reply?.pending_action && (
                    <ConfirmCard
                      action={tu.reply.pending_action}
                      busy={confirmBusy === tu.reply.pending_action.id}
                      done={actionDone[tu.reply.pending_action.id] ?? null}
                      onConfirm={(ok) => void confirmAction(tu.reply!.pending_action!, ok)}
                    />
                  )}
                  {tu.reply?.claims && tu.reply.claims.length > 0 && (
                    <details className="mt-2 text-xs opacity-90">
                      <summary className="cursor-pointer font-semibold">{t("voice.claimsTitle", { n: tu.reply.claims.length })}</summary>
                      <ul className="mt-1 space-y-0.5">
                        {tu.reply.claims.map((c, i) => (
                          <li key={i} className="flex flex-wrap gap-x-2">
                            <span className="num font-semibold">{c.rendered}</span>
                            <span className="font-mono opacity-75" lang="en">← {c.field}</span>
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                  {tu.reply && (
                    <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs">
                      {tu.reply.safety.emergency ? (
                        <a href="tel:108" className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 font-bold text-[rgb(176_56_40)]">
                          <Phone size={14} aria-hidden />
                          108
                        </a>
                      ) : tu.reply.safety.blocked ? (
                        <span className="inline-flex items-center gap-1 text-moon-2">
                          <ShieldOff size={13} aria-hidden />
                          {t("voice.blocked")}
                        </span>
                      ) : tu.reply.grounding.passed ? (
                        <span className="inline-flex items-center gap-1 text-teal" title={tu.reply.grounding.numbers?.length ? tu.reply.grounding.numbers.join(", ") : undefined}>
                          <CheckCircle2 size={13} aria-hidden />
                          {tu.reply.grounding.fallback_used ? t("voice.fallback") : t("voice.grounded")}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-coral-night">
                          <AlertTriangle size={13} aria-hidden />
                          {t("voice.notVerified")}
                        </span>
                      )}
                      {tu.reply.safety.injection && (
                        <span className="inline-flex items-center gap-1 text-moon-2">
                          <ShieldAlert size={13} aria-hidden />
                          {t("voice.injection")}
                        </span>
                      )}
                      {(tu.reply.source || tu.reply.source_detail) &&
                        (() => {
                          const src = replySource(tu.reply);
                          return (
                            <span className="rounded-full border border-night-line px-2 py-0.5 text-[0.68rem] text-moon-3" title={src.detail ?? undefined}>
                              {t(`voice.source.${src.kind}`)}
                              {src.model && (
                                <span lang="en" className="ml-1 opacity-80">
                                  · {src.model}
                                </span>
                              )}
                            </span>
                          );
                        })()}
                      <button type="button" className="inline-flex items-center gap-1 font-semibold opacity-90 hover:opacity-100" onClick={() => void speak(tu.reply as AgentReply)}>
                        <Volume2 size={13} aria-hidden />
                        {t("voice.replay")}
                      </button>
                      {(tu.reply.tool_calls?.length ?? 0) > 0 && (
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 font-semibold opacity-90 hover:opacity-100"
                          onClick={() => {
                            setToolCalls(tu.reply?.tool_calls ?? []);
                            openWhy(forecastIdOf(tu.reply?.tool_calls) ?? s?.forecast.forecast_id ?? null, tu.reply?.tool_calls ?? []);
                          }}
                        >
                          <HelpCircle size={13} aria-hidden />
                          {t("common.why")}
                        </button>
                      )}
                    </div>
                  )}
                </motion.div>
              ),
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
