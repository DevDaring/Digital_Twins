import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { m as motion, useReducedMotion } from "framer-motion";
import { ArrowRight, Eye, EyeOff, KeyRound, Loader2 } from "lucide-react";
import { useAuth } from "@/store/auth";
import { signIn } from "@/lib/session";
import { LangSwitch } from "@/components/AppShell";
import { LogoMark, MockPill } from "@/components/ui";
import { useApplyTheme } from "@/hooks/useDemo";

/** Public jury / reviewer account (synthetic demo data only). Shown on the sign-in page on purpose. */
export const JURY_USER = "TestUser";
export const JURY_PASSWORD = "TestUser11";

/** A glucose-like curve repeated twice so it can drift seamlessly. */
function riverPath(w: number, mid: number, amp: number, phase = 0) {
  const seg = w / 4;
  let d = `M0 ${mid}`;
  for (let i = 0; i < 8; i++) {
    const x0 = i * seg;
    const up = (i + phase) % 2 === 0 ? -1 : 1;
    const a = amp * (0.55 + ((i * 37) % 10) / 22);
    d += ` C${x0 + seg * 0.35} ${mid} ${x0 + seg * 0.4} ${mid + up * a} ${x0 + seg * 0.62} ${mid + up * a} S${x0 + seg * 0.9} ${mid} ${x0 + seg} ${mid}`;
  }
  return d;
}

function Reflection() {
  const reduce = useReducedMotion();
  const W = 1600;
  const drift = reduce ? "" : "animate-drift";
  const slow = reduce ? "" : "animate-drift-slow";
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      {/* stars */}
      <svg className="absolute inset-0 h-full w-full" preserveAspectRatio="none">
        {Array.from({ length: 46 }, (_, i) => (
          <circle key={i} cx={`${(i * 53) % 100}%`} cy={`${((i * 29) % 46) + 2}%`} r={i % 7 === 0 ? 1.3 : 0.7} fill="rgb(var(--moon))" opacity={0.18 + (i % 5) * 0.08} />
        ))}
      </svg>
      {/* horizon */}
      <div className="absolute inset-x-0 top-[76%] h-px bg-gradient-to-r from-transparent via-moon/30 to-transparent" />
      {/* a faint second curve, further away */}
      <div className="absolute inset-x-0 top-[63%] h-[13%] opacity-40">
        <div className={`flex h-full w-[200%] ${slow}`}>
          {[0, 1].map((k) => (
            <svg key={k} viewBox={`0 0 ${W} 200`} preserveAspectRatio="none" className="h-full w-1/2">
              <path d={riverPath(W, 170, 70, 1)} fill="none" stroke="rgb(var(--moon))" strokeOpacity="0.35" strokeWidth="1.2" />
            </svg>
          ))}
        </div>
      </div>
      {/* the twin curve above the horizon */}
      <div className="absolute inset-x-0 top-[58%] h-[18%]">
        <div className={`flex h-full w-[200%] ${drift}`}>
          {[0, 1].map((k) => (
            <svg key={k} viewBox={`0 0 ${W} 200`} preserveAspectRatio="none" className="h-full w-1/2">
              <path d={riverPath(W, 185, 120)} fill="none" stroke="rgb(var(--marigold))" strokeWidth="3" strokeLinecap="round" />
            </svg>
          ))}
        </div>
      </div>
      {/* its reflection below the horizon: mirrored, softer, rippled */}
      <div
        className="absolute inset-x-0 top-[76%] h-[18%] opacity-60 [filter:blur(1.4px)]"
        style={{ maskImage: "linear-gradient(to bottom, black, transparent 90%)", WebkitMaskImage: "linear-gradient(to bottom, black, transparent 90%)" }}
      >
        <div className={`flex h-full w-[200%] -scale-y-100 ${drift}`}>
          {[0, 1].map((k) => (
            <svg key={k} viewBox={`0 0 ${W} 200`} preserveAspectRatio="none" className="h-full w-1/2">
              <path d={riverPath(W, 185, 120)} fill="none" stroke="rgb(var(--marigold))" strokeOpacity="0.6" strokeWidth="3" strokeDasharray="26 12" />
            </svg>
          ))}
        </div>
      </div>
      {/* water ripples */}
      <div className="absolute inset-x-0 top-[80%] space-y-4 px-[8%]">
        {[0.14, 0.1, 0.07, 0.04].map((o, i) => (
          <motion.div
            key={i}
            className="h-px bg-moon"
            style={{ opacity: o, marginLeft: `${i * 9}%`, marginRight: `${(3 - i) * 7}%` }}
            animate={reduce ? undefined : { x: [0, 18, 0] }}
            transition={{ duration: 7 + i * 2, repeat: Infinity, ease: "easeInOut" }}
          />
        ))}
      </div>
    </div>
  );
}

export function LoginPage() {
  const { t } = useTranslation();
  const token = useAuth((s) => s.token);
  const navigate = useNavigate();
  const loc = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useApplyTheme();

  const from = (loc.state as { from?: string } | null)?.from ?? "/";
  if (token) return <Navigate to={from === "/login" ? "/" : from} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError(t("login.invalid"));
      return;
    }
    setBusy(true);
    setError(null);
    const res = await signIn(username.trim(), password);
    setBusy(false);
    if (res.ok) navigate(from === "/login" ? "/" : from, { replace: true });
    else setError(res.reason === "invalid" ? t("login.invalid") : t("login.error"));
  };

  return (
    <div className="stage on-night relative flex min-h-[100dvh] flex-col overflow-hidden">
      <Reflection />
      <header className="relative z-10 flex items-center justify-between px-5 py-4 sm:px-8">
        <span className="inline-flex items-center gap-2.5">
          <LogoMark size={34} />
          <span className="text-sm font-semibold text-moon-2">{t("app.name")}</span>
        </span>
        <div className="flex items-center gap-2">
          <MockPill tone="night" />
          <LangSwitch tone="night" />
        </div>
      </header>

      <main className="relative z-10 mx-auto grid w-full max-w-6xl flex-1 items-center gap-10 px-5 pb-10 pt-4 sm:px-8 lg:grid-cols-[1.15fr_0.85fr] lg:pb-[28vh]">
        <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }} className="max-w-xl">
          <h1 className="text-[3.1rem] font-extrabold leading-[0.95] tracking-[-0.035em] text-moon sm:text-7xl" lang="en">
            {t("app.name")}
          </h1>
          <p className="mt-2 text-lg font-medium text-marigold" lang="hi">
            {t("app.nativeName")}
          </p>
          <p className="mt-6 text-xl font-semibold leading-snug text-moon sm:text-2xl">{t("app.tagline")}</p>
          <p className="mt-3 max-w-md leading-relaxed text-moon-2">{t("login.intro")}</p>
        </motion.section>

        <motion.form
          onSubmit={submit}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.15 }}
          className="w-full rounded-4xl border border-night-line/70 bg-night-2/80 p-6 shadow-lift backdrop-blur-md sm:p-8 lg:justify-self-end lg:max-w-md"
          aria-labelledby="login-title"
          noValidate
        >
          <h2 id="login-title" className="text-xl font-bold text-moon">
            {t("login.title")}
          </h2>
          <section
            aria-labelledby="jury-title"
            className="mt-4 rounded-3xl border border-marigold/50 bg-marigold/10 p-4"
            data-testid="jury-access"
          >
            <p id="jury-title" className="flex items-center gap-2 text-sm font-bold text-marigold">
              <KeyRound size={16} aria-hidden /> {t("login.jury.title")}
            </p>
            <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="text-moon-2">{t("login.username")}</dt>
              <dd className="font-mono font-semibold text-moon" lang="en">{JURY_USER}</dd>
              <dt className="text-moon-2">{t("login.password")}</dt>
              <dd className="font-mono font-semibold text-moon" lang="en">{JURY_PASSWORD}</dd>
            </dl>
            <button
              type="button"
              className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-full border border-marigold/60 px-4 text-sm font-semibold text-marigold hover:bg-marigold/15 focus-visible:outline focus-visible:outline-2 focus-visible:outline-marigold"
              onClick={() => {
                setUsername(JURY_USER);
                setPassword(JURY_PASSWORD);
                setError(null);
              }}
            >
              {t("login.jury.fill")}
            </button>
            <p className="mt-2 text-xs leading-relaxed text-moon-3">{t("login.jury.note")}</p>
          </section>
          <div className="mt-6 space-y-4">
            <div>
              <label htmlFor="username" className="mb-1.5 block text-sm font-semibold text-moon-2">
                {t("login.username")}
              </label>
              <input
                id="username"
                name="username"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded-2xl border border-night-line bg-night px-4 py-3 text-base text-moon placeholder:text-moon-3 focus:border-marigold focus:outline-none focus:ring-2 focus:ring-marigold/40"
                required
              />
            </div>
            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-semibold text-moon-2">
                {t("login.password")}
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={show ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-2xl border border-night-line bg-night px-4 py-3 pr-12 text-base text-moon focus:border-marigold focus:outline-none focus:ring-2 focus:ring-marigold/40"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShow((s) => !s)}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-full p-2 text-moon-2 hover:text-moon"
                  aria-label={show ? t("login.hidePassword") : t("login.showPassword")}
                  aria-pressed={show}
                >
                  {show ? <EyeOff size={18} aria-hidden /> : <Eye size={18} aria-hidden />}
                </button>
              </div>
            </div>
          </div>
          {error && (
            <p role="alert" className="mt-4 rounded-2xl bg-coral/15 px-4 py-3 text-sm font-medium text-coral-night">
              {error}
            </p>
          )}
          <button type="submit" className="btn-marigold mt-6 h-12 w-full text-base" disabled={busy}>
            {busy ? <Loader2 size={18} className="animate-spin" aria-hidden /> : null}
            {busy ? t("login.signingIn") : t("login.submit")}
            {!busy && <ArrowRight size={18} aria-hidden />}
          </button>
        </motion.form>
      </main>
      <footer className="relative z-10 px-5 pb-6 text-center text-xs leading-relaxed text-moon-3">
        <p className="mx-auto max-w-3xl">{t("footer.disclaimer")}</p>
      </footer>
    </div>
  );
}
