import { useTranslation } from "react-i18next";
import { Moon, Activity } from "lucide-react";
import { useActivePatientId, usePatient } from "@/api/hooks";
import { OutlookCard } from "@/components/clinical";
import { Avatar, ErrorState, PageHeader, SyntheticBadge } from "@/components/ui";
import { Sparkline } from "@/charts/SmallCharts";
import { pct } from "@/lib/format";

export default function ProfilePage() {
  const { t } = useTranslation();
  const pid = useActivePatientId();
  const q = usePatient(pid);
  const p = q.data;
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <PageHeader title={t("me.title")} />
      {q.isError && <ErrorState message={t("errors.generic")} onRetry={() => void q.refetch()} />}
      {q.isLoading && <div className="skeleton h-48" />}
      {p && (
        <div className="grid gap-5">
          <section className="stage on-night flex flex-col gap-5 rounded-4xl p-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-4">
              <Avatar initials={p.avatar_initials} size={64} active />
              <div>
                <h2 className="text-2xl font-extrabold text-moon">{p.name}</h2>
                <p className="text-moon-2">
                  <span className="num">{p.age}</span> · {p.sex === "F" ? t("common.female") : t("common.male")} · {p.city} · {p.occupation}
                </p>
                <div className="mt-2">
                  <SyntheticBadge tone="night" note={p.source_note} />
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-6">
              <div>
                <p className="eyebrow text-moon-3">{t("doctor.tir")}</p>
                <p className="num text-3xl font-extrabold text-teal">{pct(p.tir_7d)}%</p>
              </div>
              <div>
                <p className="eyebrow text-moon-3">{t("doctor.hba1c")}</p>
                <p className="num text-3xl font-extrabold text-moon">{p.hba1c.toFixed(1)}%</p>
              </div>
              <div className="self-end">
                <Sparkline values={p.sparkline} tone="moon" />
              </div>
            </div>
          </section>
          <div className="grid gap-5 md:grid-cols-2">
            <section className="card p-5">
              <h2 className="flex items-center gap-2 font-bold">
                <Activity size={17} className="text-marigold-ink" aria-hidden />
                {t("me.calibrated", { n: p.calibration.cgm_days })}
              </h2>
              <p className="mt-3 flex items-center gap-2 text-sm text-ink-2">
                <Moon size={16} aria-hidden />
                {t("me.sleep", { start: p.sleep_window.start, end: p.sleep_window.end })}
              </p>
              <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("me.source")}</p>
              <p className="mt-1 text-sm text-ink-2" lang="en">
                {p.source_note}
              </p>
            </section>
            <section className="card p-5">
              <h2 className="font-bold">{t("doctor.record")}</h2>
              <p className="mt-2 text-sm" lang="en">
                {p.ehr.conditions.join(" · ")}
              </p>
              <p className="mt-2 text-sm text-ink-2" lang="en">
                {p.ehr.medications.join(" · ")}
              </p>
              <p className="mt-2 text-sm text-ink-2">
                {t("doctor.bmi")} <span className="num font-semibold text-ink">{p.ehr.bmi.toFixed(1)}</span> · {t("doctor.diabetesYears", { n: p.ehr.diabetes_years })}
              </p>
            </section>
          </div>
          <OutlookCard patientId={p.id} />
        </div>
      )}
    </div>
  );
}
