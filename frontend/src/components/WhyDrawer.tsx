import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Brain, ChevronRight, Download, FileCheck2, HeartPulse, Loader2, Wrench } from "lucide-react";
import type { ClaimStatus, Driver, Lang, Receipt, ReceiptClaim } from "@/api/types";
import { CLAIM_STATUSES } from "@/api/types";
import { api } from "@/api";
import { ApiError } from "@/api/http";
import { useActivePatientId, useExplain, useReceipt } from "@/api/hooks";
import { SignedBars } from "@/charts/TrustCharts";
import { formatClock, formatDateTime, signed } from "@/lib/format";
import { driverLabel } from "@/lib/drivers";
import { downloadText, isClaimStatus, receiptToMarkdown } from "@/lib/evidence";
import { useApp } from "@/store/app";
import { toast } from "@/store/toast";
import { EvidenceChip } from "./evidence";
import { ErrorState, Modal } from "./ui";

function useDriverLabel() {
  const { t, i18n } = useTranslation();
  return (d: Driver) => driverLabel(t, i18n, d);
}

function DriverGroup({ title, hint, drivers, icon }: { title: string; hint: string; drivers: Driver[]; icon: ReactNode }) {
  const { t } = useTranslation();
  const label = useDriverLabel();
  const sorted = drivers.slice().sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
  return (
    <section className="card p-5">
      <h3 className="flex items-center gap-2 font-bold">
        {icon}
        {title}
      </h3>
      <p className="mb-4 text-sm text-ink-3">{hint}</p>
      {sorted.length ? (
        <SignedBars items={sorted.map((d, i) => ({ key: `${d.name}-${i}`, label: label(d), value: d.contribution }))} format={(v) => t("why.contribution", { sign: "", n: signed(v, 1) })} />
      ) : (
        <p className="text-sm text-ink-3">{t("why.noDrivers")}</p>
      )}
    </section>
  );
}

const PROB_UNITS = ["probability", "proportion"];
const fmtNum = (v: number) => (Math.abs(v) >= 10 ? String(Math.round(v)) : String(Math.round(v * 10) / 10));

/** Value of a receipt claim for display: probabilities as "about N in 10", ranges as lo–hi, times as a clock. */
function claimValue(t: (k: string, o?: Record<string, unknown>) => string, lang: string, c: ReceiptClaim): string {
  const v = c.value;
  const unit = c.unit ?? "";
  if (v === null || v === undefined || v === "") return "—";
  const isProb = PROB_UNITS.includes(unit) || (!unit && typeof v === "number" && v >= 0 && v <= 1 && /p_|prob|risk|chance/i.test(c.key));
  if (Array.isArray(v)) {
    const nums = v.filter((x): x is number => typeof x === "number" && Number.isFinite(x));
    return nums.length ? `${nums.map(fmtNum).join("–")}${unit && !isProb ? ` ${unit}` : ""}` : "—";
  }
  if (unit === "time" && typeof v === "string") return formatClock(v, lang);
  if (typeof v === "number") {
    if (isProb) return t("receipt.outOfTen", { n: Math.round(v * 10), pct: Math.round(v * 100) });
    return `${fmtNum(v)}${unit ? ` ${unit}` : ""}`;
  }
  return `${v}${unit && unit !== "time" ? ` ${unit}` : ""}`;
}

/** Extra detail under a claim: held-out reliability interval and size, or a note. */
function claimExtra(t: (k: string, o?: Record<string, unknown>) => string, c: ReceiptClaim): string | null {
  const ci = Array.isArray(c.ci) ? (c.ci as unknown[]).filter((x): x is number => typeof x === "number") : [];
  if (ci.length === 2 && typeof c.n === "number") return t("risk.reliabilityCi", { lo: Math.round(ci[0] * 10), hi: Math.round(ci[1] * 10), n: c.n.toLocaleString("en-IN") });
  return null;
}

function KeyValues({ data }: { data: Record<string, unknown> | undefined }) {
  const entries = Object.entries(data ?? {}).filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (!entries.length) return null;
  const show = (v: unknown): string => {
    if (typeof v === "object" && v !== null) {
      if ("value" in (v as Record<string, unknown>)) {
        const o = v as { value: unknown; source?: unknown; date?: unknown };
        return [String(o.value), o.source ? `(${String(o.source)}${o.date ? `, ${String(o.date)}` : ""})` : ""].filter(Boolean).join(" ");
      }
      return Object.entries(v as Record<string, unknown>)
        .map(([k, x]) => `${k}: ${show(x)}`)
        .join(" · ");
    }
    return String(v);
  };
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs" lang="en">
      {entries.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="font-mono text-ink-3">{k}</dt>
          <dd className="break-words text-ink-2">{show(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

function ReceiptView({ pid, forecastId }: { pid: string; forecastId: string }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language as Lang;
  const q = useReceipt(pid, forecastId, lang);
  const [busy, setBusy] = useState(false);
  const r: Receipt | undefined = q.data;
  const statusLabel = (s: ClaimStatus) => t(`evidence.status.${s}`);

  const download = async () => {
    if (!r) return;
    setBusy(true);
    try {
      let md: string;
      try {
        md = await api.receiptMarkdown(pid, forecastId, lang);
      } catch {
        md = receiptToMarkdown(r, { title: t("receipt.title"), status: statusLabel, claim: t("receipt.claim"), value: t("receipt.value"), source: t("receipt.source") });
      }
      downloadText(md, `pratifalan-receipt-${forecastId}.md`);
    } catch {
      toast(t("errors.generic"), "error");
    } finally {
      setBusy(false);
    }
  };

  if (q.isLoading) return <div className="skeleton h-48" />;
  if (q.isError) {
    const notFound = q.error instanceof ApiError && (q.error.status === 404 || q.error.status === 403);
    return <ErrorState message={notFound ? t("receipt.notFound") : t("receipt.unavailable")} onRetry={notFound ? undefined : () => void q.refetch()} />;
  }
  if (!r) return null;
  const counts = CLAIM_STATUSES.map((s) => ({ s, n: r.claims.filter((c) => c.status === s).length })).filter((x) => x.n > 0);
  return (
    <section className="card p-5" aria-labelledby="receipt-title">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 id="receipt-title" className="flex items-center gap-2 font-bold">
            <FileCheck2 size={17} className="text-teal-ink" aria-hidden />
            {t("receipt.title")}
          </h3>
          <p className="text-xs text-ink-3">
            {t("receipt.meta", { now: formatDateTime(r.replay_now, lang), made: formatDateTime(r.generated_at, lang) })}
          </p>
        </div>
        <button type="button" className="btn-ghost h-10 min-h-0 px-3.5 text-sm" onClick={() => void download()} disabled={busy}>
          {busy ? <Loader2 size={15} className="animate-spin" aria-hidden /> : <Download size={15} aria-hidden />}
          {t("receipt.download")}
        </button>
      </div>
      <p className="mt-2 flex flex-wrap gap-1.5" aria-label={t("receipt.summary")}>
        {counts.map(({ s, n }) => (
          <span key={s} className="inline-flex items-center gap-1 text-xs text-ink-2">
            <EvidenceChip status={s} explain={false} /> <span className="num">×{n}</span>
          </span>
        ))}
      </p>
      <ul className="mt-3 divide-y divide-line">
        {r.claims.map((c, i) => {
          const status = isClaimStatus(c.status) ? c.status : "estimated";
          const localKey = `receipt.claims.${c.key}`;
          // Backend label in the requested language first, then our own translation, then English.
          const backendLocal = typeof c.label === "string" && c.label && (lang === "en-IN" || c.label !== c.label_en) ? c.label : null;
          const translated = !backendLocal && i18n.exists(localKey);
          const label = backendLocal ?? (translated ? t(localKey) : c.label_en);
          const english = !backendLocal && !translated && lang !== "en-IN";
          const extra = claimExtra(t, c);
          const note = typeof c.note === "string" ? c.note : null;
          return (
            <li key={`${c.key}-${i}`} className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold" lang={english ? "en" : undefined}>
                  {label}
                </p>
                <p className="break-words text-[0.7rem] text-ink-3" lang="en">
                  {t(`receipt.kind.${c.source.kind}`, { defaultValue: c.source.kind })}: {c.source.ref}
                </p>
                {note && (
                  <p className="break-words text-[0.7rem] text-ink-3" lang="en">
                    {note}
                  </p>
                )}
              </div>
              <div className="flex max-w-[45%] flex-col items-end gap-1 text-right">
                <span className="num text-sm font-bold">{claimValue(t, lang, c)}</span>
                {extra && <span className="num text-[0.7rem] text-ink-3">{extra}</span>}
                <EvidenceChip status={status} />
              </div>
            </li>
          );
        })}
      </ul>
      <details className="mt-3 rounded-2xl bg-paper-2 p-3 text-sm">
        <summary className="cursor-pointer font-semibold">{t("receipt.legendTitle")}</summary>
        <ul className="mt-2 space-y-2">
          {CLAIM_STATUSES.map((s) => (
            <li key={s} className="flex flex-col gap-1">
              <span>
                <EvidenceChip status={s} explain={false} />
              </span>
              <span className="text-xs leading-relaxed text-ink-2">{t(`evidence.explain.${s}`)}</span>
            </li>
          ))}
        </ul>
      </details>
      {(Object.keys(r.model ?? {}).length > 0 || Object.keys(r.inputs ?? {}).length > 0) && (
        <details className="mt-2 rounded-2xl border border-line p-3">
          <summary className="cursor-pointer text-sm font-semibold">{t("receipt.provenance")}</summary>
          <div className="mt-2 space-y-3">
            <div>
              <p className="eyebrow mb-1 text-ink-3">{t("receipt.model")}</p>
              <KeyValues data={r.model} />
            </div>
            <div>
              <p className="eyebrow mb-1 text-ink-3">{t("receipt.inputs")}</p>
              <KeyValues data={r.inputs} />
            </div>
          </div>
        </details>
      )}
    </section>
  );
}

/** "Why?" drawer: the evidence receipt, ranked drivers split by source, and the tool calls behind them. */
export function WhyDrawer() {
  const { t, i18n } = useTranslation();
  const open = useApp((s) => s.whyOpen);
  const close = useApp((s) => s.closeWhy);
  const pid = useActivePatientId();
  const q = useExplain(pid, open?.forecastId ?? null);

  return (
    <Modal open={!!open} onClose={close} title={t("why.title")} subtitle={t("why.subtitle")} variant="drawer">
      <div className="space-y-4 pt-2">
        {open?.forecastId && pid && <ReceiptView pid={pid} forecastId={open.forecastId} />}
        {open?.forecastId &&
          (q.isLoading ? (
            <div className="space-y-3">
              <div className="skeleton h-40" />
            </div>
          ) : q.isError ? (
            <ErrorState message={q.error instanceof ApiError && q.error.status === 404 ? t("receipt.notFound") : t("errors.generic")} onRetry={() => void q.refetch()} />
          ) : q.data ? (
            <>
              {(() => {
                const top = (q.data.physiology ?? []).slice().sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))[0];
                const text = top ? t("why.summaryText", { name: driverLabel(t, i18n, top), n: signed(top.contribution) }) : i18n.language === "en-IN" ? q.data.text_en : "";
                return text ? (
                  <p className="rounded-2xl bg-paper-2 p-4 text-sm leading-relaxed">
                    <span className="font-semibold">{t("why.summary")}: </span>
                    {text}
                  </p>
                ) : null;
              })()}
              <DriverGroup title={t("why.physiology")} hint={t("why.physiologyHint")} drivers={q.data.physiology ?? []} icon={<HeartPulse size={17} className="text-coral-ink" aria-hidden />} />
              <DriverGroup title={t("why.learned")} hint={t("why.learnedHint")} drivers={q.data.learned ?? []} icon={<Brain size={17} className="text-violet-ink" aria-hidden />} />
              <p className="text-xs text-ink-3">{t("why.caption")}</p>
            </>
          ) : null)}

        <section className="card p-5">
          <h3 className="flex items-center gap-2 font-bold">
            <Wrench size={16} className="text-ink-3" aria-hidden />
            {open?.toolCalls ? t("why.toolCalls") : t("why.toolCallsForecast")}
          </h3>
          <p className="mb-3 text-sm text-ink-3">{t("why.toolCallsHint")}</p>
          {(() => {
            const calls = open?.toolCalls ?? q.data?.tool_calls ?? [];
            if (!calls.length) return <p className="text-sm text-ink-3">{open?.toolCalls ? t("why.noToolCalls") : t("why.noToolCallsForecast")}</p>;
            return (
              <ul className="space-y-2">
                {calls.map((c, i) => (
                  <li key={i}>
                    <details className="group rounded-2xl border border-line bg-paper">
                      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 font-mono text-sm font-semibold">
                        <ChevronRight size={15} className="transition group-open:rotate-90" aria-hidden />
                        {c.name}
                      </summary>
                      <pre className="max-h-72 overflow-auto border-t border-line px-4 py-3 text-xs leading-relaxed text-ink-2" lang="en">
                        {JSON.stringify({ args: c.args, output: c.output }, null, 2)}
                      </pre>
                    </details>
                  </li>
                ))}
              </ul>
            );
          })()}
        </section>
      </div>
    </Modal>
  );
}
