"""Evidence receipt (contract v3, C4): every important number behind one forecast, with its
status (measured / estimated / simulated / validated / exploratory / not_validated) and its
source (a tool output, an evaluation report, the dataset, or the user)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pratifalan.twin.engine import M_FC, VALIDATED_HORIZON_MIN, TwinEngine

LABELS: dict[str, dict[str, str]] = {
    "last_reading": {"en-IN": "Last glucose reading", "hi-IN": "आख़िरी शुगर रीडिंग", "bn-IN": "শেষ সুগার রিডিং",
                     "kn-IN": "ಕೊನೆಯ ಸಕ್ಕರೆ ರೀಡಿಂಗ್"},
    "estimate_now": {"en-IN": "Current glucose estimate", "hi-IN": "अभी की शुगर का अनुमान",
                     "bn-IN": "এখনকার সুগারের অনুমান", "kn-IN": "ಈಗಿನ ಸಕ್ಕರೆಯ ಅಂದಾಜು"},
    "band_now": {"en-IN": "Likely range now (90%)", "hi-IN": "अभी का संभावित दायरा (90%)",
                 "bn-IN": "এখনকার সম্ভাব্য সীমা (90%)", "kn-IN": "ಈಗಿನ ಸಂಭಾವ್ಯ ವ್ಯಾಪ್ತಿ (90%)"},
    "forecast_peak": {"en-IN": "Expected peak in the next 2 hours", "hi-IN": "अगले 2 घंटों में अनुमानित उच्चतम स्तर",
                      "bn-IN": "পরের 2 ঘণ্টায় আনুমানিক সর্বোচ্চ মাত্রা", "kn-IN": "ಮುಂದಿನ 2 ಗಂಟೆಗಳ ಅಂದಾಜು ಗರಿಷ್ಠ ಮಟ್ಟ"},
    "p_high": {"en-IN": "Chance of going above 180 in 2 hours", "hi-IN": "2 घंटों में 180 से ऊपर जाने की संभावना",
               "bn-IN": "2 ঘণ্টায় 180-এর ওপরে যাওয়ার সম্ভাবনা", "kn-IN": "2 ಗಂಟೆಗಳಲ್ಲಿ 180 ಮೀರುವ ಸಾಧ್ಯತೆ"},
    "p_high_reliability": {"en-IN": "How often this happened for similar held-out forecasts",
                           "hi-IN": "मिलते-जुलते जाँच वाले अनुमानों में यह कितनी बार हुआ",
                           "bn-IN": "একই রকম যাচাই-পূর্বাভাসে এটা কতবার ঘটেছে",
                           "kn-IN": "ಇಂತಹ ಪರೀಕ್ಷಾ ಮುನ್ಸೂಚನೆಗಳಲ್ಲಿ ಇದು ಎಷ್ಟು ಬಾರಿ ಆಯಿತು"},
    "p_low": {"en-IN": "Chance of going below 70 in 2 hours (not validated)",
              "hi-IN": "2 घंटों में 70 से नीचे जाने की संभावना (प्रमाणित नहीं)",
              "bn-IN": "2 ঘণ্টায় 70-এর নিচে নামার সম্ভাবনা (যাচাই করা হয়নি)",
              "kn-IN": "2 ಗಂಟೆಗಳಲ್ಲಿ 70 ಕ್ಕಿಂತ ಕೆಳಗೆ ಹೋಗುವ ಸಾಧ್ಯತೆ (ಪರಿಶೀಲಿತವಲ್ಲ)"},
    "trajectory_240": {"en-IN": "Median curve at 4 hours (beyond the validated 2 hours)",
                       "hi-IN": "4 घंटे पर मध्य वक्र (प्रमाणित 2 घंटों से आगे)",
                       "bn-IN": "4 ঘণ্টায় মধ্য রেখা (যাচাই করা 2 ঘণ্টার পরে)",
                       "kn-IN": "4 ಗಂಟೆಯಲ್ಲಿ ಮಧ್ಯ ವಕ್ರ (ಪರಿಶೀಲಿತ 2 ಗಂಟೆಗಳ ನಂತರ)"},
    "meal_carbs": {"en-IN": "Meal carbohydrate", "hi-IN": "भोजन के कार्ब्स", "bn-IN": "খাবারের কার্বস",
                   "kn-IN": "ಊಟದ ಕಾರ್ಬ್ಸ್"},
    "hba1c": {"en-IN": "HbA1c used by the twin", "hi-IN": "ट्विन द्वारा इस्तेमाल HbA1c", "bn-IN": "টুইন যে HbA1c ব্যবহার করছে",
              "kn-IN": "ಟ್ವಿನ್ ಬಳಸುವ HbA1c"},
    "bmi": {"en-IN": "BMI used by the twin", "hi-IN": "ट्विन द्वारा इस्तेमाल BMI", "bn-IN": "টুইন যে BMI ব্যবহার করছে",
            "kn-IN": "ಟ್ವಿನ್ ಬಳಸುವ BMI"},
    "top_driver": {"en-IN": "Biggest physiology driver of the peak", "hi-IN": "उच्चतम स्तर का सबसे बड़ा शारीरिक कारण",
                   "bn-IN": "সর্বোচ্চ মাত্রার সবচেয়ে বড় শারীরিক কারণ", "kn-IN": "ಗರಿಷ್ಠ ಮಟ್ಟದ ದೊಡ್ಡ ದೈಹಿಕ ಕಾರಣ"},
    "next_check": {"en-IN": "Suggested next finger-prick (experimental)", "hi-IN": "अगली उँगली जाँच का सुझाव (प्रायोगिक)",
                   "bn-IN": "পরের আঙুল-পরীক্ষার পরামর্শ (পরীক্ষামূলক)", "kn-IN": "ಮುಂದಿನ ಬೆರಳಿನ ಪರೀಕ್ಷೆಯ ಸಲಹೆ (ಪ್ರಾಯೋಗಿಕ)"},
    "scenario_peak": {"en-IN": "Simulated peak with the change", "hi-IN": "बदलाव के साथ सिम्युलेटेड उच्चतम स्तर",
                      "bn-IN": "বদলসহ সিমুলেটেড সর্বোচ্চ মাত্রা", "kn-IN": "ಬದಲಾವಣೆಯೊಂದಿಗೆ ಸಿಮ್ಯುಲೇಟೆಡ್ ಗರಿಷ್ಠ ಮಟ್ಟ"},
    "scenario_p_high": {"en-IN": "Simulated chance above 180 with the change",
                        "hi-IN": "बदलाव के साथ 180 से ऊपर जाने की सिम्युलेटेड संभावना",
                        "bn-IN": "বদলসহ 180-এর ওপরে যাওয়ার সিমুলেটেড সম্ভাবনা",
                        "kn-IN": "ಬದಲಾವಣೆಯೊಂದಿಗೆ 180 ಮೀರುವ ಸಿಮ್ಯುಲೇಟೆಡ್ ಸಾಧ್ಯತೆ"},
}

STATUS_EN = {"measured": "measured", "estimated": "estimated by the twin", "simulated": "model simulation",
             "validated": "checked on held-out data", "exploratory": "exploratory", "not_validated": "not validated"}


def _claim(key: str, lang: str, value: Any, unit: str, status: str, kind: str, ref: str, **extra: Any) -> dict:
    lab = LABELS.get(key, {"en-IN": key})
    return {"key": key, "label_en": lab["en-IN"], "label": lab.get(lang, lab["en-IN"]), "value": value, "unit": unit,
            "status": status, "source": {"kind": kind, "ref": ref}, **extra}


def _reading_source(src: str | None) -> tuple[str, str]:
    if src in ("manual", "chat"):
        return "user", f"reading entered by the user ({src})"
    if src == "replay":
        return "dataset", "dataset reference CGM revealed in the replay"
    return "dataset", "sensor-ladder observation from the persona's open CGMacros record"


def build(engine: TwinEngine, ctx: dict, forecast_id: str, persona: dict, lang: str) -> dict:
    pid, ladder = ctx["pid"], ctx["ladder"]
    events, offset, rev = ctx.get("events", []), int(ctx.get("offset", 0)), ctx.get("rev")
    out = ctx["out"]
    st = engine.state(pid, ladder, events, offset=offset, rev=rev)
    prov = out.get("provenance") or {}
    claims: list[dict] = []
    last = st.get("last_observation")
    if last:
        kind, ref = _reading_source(last.get("source"))
        claims.append(_claim("last_reading", lang, last["value"], "mg/dL", "measured", kind, ref, t=last["t"]))
    claims.append(_claim("estimate_now", lang, st["estimate"], "mg/dL", "estimated", "tool", "get_state.estimate",
                         t=st["now"]))
    claims.append(_claim("band_now", lang, [st["band"]["lo"], st["band"]["hi"]], "mg/dL", "estimated", "tool",
                         "get_state.band"))
    if ctx.get("kind") == "scenario":
        claims.append(_claim("scenario_peak", lang, out["peak"]["value"], "mg/dL", "simulated", "tool",
                             "what_if.scenario.peak", t=out["peak"]["t"], baseline_forecast_id=ctx.get("baseline_id")))
        claims.append(_claim("scenario_p_high", lang, out["p_high"]["p"], "probability", "simulated", "tool",
                             "what_if.scenario.p_high.p"))
    else:
        claims.append(_claim("forecast_peak", lang, out["peak"]["value"], "mg/dL", "estimated", "tool",
                             "forecast.peak", t=out["peak"]["t"]))
        rel = out["p_high"].get("reliability") or {}
        claims.append(_claim("p_high", lang, out["p_high"]["p"], "probability", "validated", "tool",
                             "forecast.p_high.p", freq_text=out["p_high"].get("freq_text")))
        claims.append(_claim("p_high_reliability", lang, rel.get("observed"), "proportion", "validated", "report",
                             f"reports/calibration_curve.json#levels.{ladder}.high",
                             n=rel.get("n"), ci=[rel.get("ci_lo"), rel.get("ci_hi")],
                             bin=[rel.get("pred_lo"), rel.get("pred_hi")]))
    claims.append(_claim("p_low", lang, out["p_low"]["p"], "probability", "not_validated", "tool", "forecast.p_low.p"))
    q50 = out["traj"]["q50"]
    if out.get("horizon_min", 0) > VALIDATED_HORIZON_MIN and q50:
        claims.append(_claim("trajectory_240", lang, q50[-1], "mg/dL", "exploratory", "tool", "forecast.traj.q50[-1]",
                             t=out["traj"]["t"][-1]))
    meal = ctx.get("meal")
    if meal and meal.get("carbs") is not None:
        claims.append(_claim("meal_carbs", lang, meal.get("carbs"), "g", "estimated", "user",
                             "meal input; nutrition from the Indian food table", name=meal.get("name")))
    for k, unit in (("hba1c", "%"), ("bmi", "kg/m2")):
        pi = (prov.get("prior_inputs") or {}).get(k) or {}
        if pi.get("source") == "lab upload (confirmed)":
            claims.append(_claim(k, lang, pi.get("value"), unit, "measured", "user",
                                 f"lab upload revision {pi.get('revision')}, collected {pi.get('date') or 'date unknown'}"))
        else:
            claims.append(_claim(k, lang, pi.get("value"), unit, "measured", "dataset",
                                 "persona EHR (open CGMacros source participant)"))
    if ctx.get("kind") == "forecast":
        phys = ctx.get("phys") or []
        if phys:
            top = sorted(phys, key=lambda d: -abs(d["contribution"]))[0]
            claims.append(_claim("top_driver", lang, top["contribution"], "mg/dL on the peak", "simulated", "tool",
                                 f"explain.physiology.{top['name']}", driver=top["label_en"]))
    nbp = st.get("next_best_prick") or {}
    if nbp.get("time"):
        claims.append(_claim("next_check", lang, nbp["time"], "time", "exploratory", "tool", "next_best_prick.time",
                             note="reports/nbp_value.json: no significant accuracy gain shown"))
    ev_out = []
    for e in events:
        t_min = float(e.get("t_min") or 0.0)
        item = {"kind": e.get("kind"), "t": engine.display_time(pid, t_min).isoformat(timespec="minutes"),
                "source": e.get("source", "manual")}
        if e.get("kind") == "reading":
            item["value_mg_dl"] = e.get("value")
        else:
            item.update({"name": e.get("name"), "carbs": e.get("carbs")})
        ev_out.append(item)
    return {
        "forecast_id": forecast_id, "persona_id": pid, "persona_name": persona.get("name"), "synthetic": True,
        "kind": ctx.get("kind", "forecast"), "replay_now": prov.get("replay_now", st["now"]),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "claims": claims,
        "inputs": {"ladder": ladder, "offset_min": offset, "events": ev_out, "meal": meal,
                   "scenario": ctx.get("scenario"), "covariate_revision": prov.get("inputs_revision", 0),
                   "prior_inputs": prov.get("prior_inputs"), "observations_used": prov.get("observations_used")},
        "model": {"model_version": prov.get("model_version", engine.model_version),
                  "hybrid_trained_on": prov.get("hybrid_trained_on", engine.hybrid_trained_on),
                  "conformal_level": out.get("conformal_level", 0.9), "validated_horizon_min": VALIDATED_HORIZON_MIN,
                  "forecast_particles": M_FC,
                  "calibration": "after a 5-day CGM calibration wear (persona replay)",
                  "notes": ["P(>180 in 2 h) reliability comes from patient-grouped held-out forecasts "
                            "(reports/calibration_curve.json).", "P(<70) is not validated.",
                            "Trajectory points beyond 120 minutes are exploratory.",
                            "What-if results are model simulations, not proven effects."]},
        "tool_calls": [
            {"name": "get_state", "args": {"ladder": ladder, "offset_min": offset},
             "output": {"estimate": st["estimate"], "band": st["band"], "now": st["now"],
                        "last_observation": st.get("last_observation")}},
            {"name": "what_if" if ctx.get("kind") == "scenario" else "forecast",
             "args": {"ladder": ladder, "meal": meal, "scenario": ctx.get("scenario"), "offset_min": offset},
             "output": {"forecast_id": forecast_id, "peak": out["peak"], "p_high": out["p_high"]["p"],
                        "p_low": out["p_low"]["p"]}},
        ],
    }


def _fmt(v: Any) -> str:
    if isinstance(v, list):
        return " to ".join(_fmt(x) for x in v)
    if isinstance(v, float):
        return f"{v:g}"
    return "n/a" if v is None else str(v)


def markdown(r: dict) -> str:
    lines = [f"# Evidence receipt: {r.get('persona_name') or r['persona_id']} (synthetic persona)", "",
             f"- Forecast id: `{r['forecast_id']}` ({r.get('kind', 'forecast')})",
             f"- Replay time: {r['replay_now']} (replay clock, not wall-clock time)",
             f"- Generated: {r['generated_at']}", "",
             "Decision support only; not a medical device. No medicine or insulin dose advice.", "",
             "## Claims", "", "| Claim | Value | Unit | Status | Source |", "|---|---|---|---|---|"]
    for c in r["claims"]:
        src = c["source"]
        lines.append(f"| {c['label_en']} | {_fmt(c['value'])} | {c['unit']} | {STATUS_EN.get(c['status'], c['status'])} "
                     f"| {src['kind']}: {src['ref']} |")
    inp = r["inputs"]
    lines += ["", "## Inputs", "", f"- Sensor ladder: {inp['ladder']}; replay offset {inp['offset_min']} min",
              f"- Covariate revision: {inp['covariate_revision']}",
              f"- Observations used: {inp.get('observations_used')}"]
    for k, v in (inp.get("prior_inputs") or {}).items():
        lines.append(f"- Prior input {k}: {_fmt(v.get('value'))} ({v.get('source')}"
                     + (f", {v.get('date')}" if v.get("date") else "") + ")")
    for e in inp.get("events") or []:
        what = f"{e.get('value_mg_dl')} mg/dL reading" if e["kind"] == "reading" else f"meal {e.get('name')} ({e.get('carbs')} g)"
        lines.append(f"- User event at {e['t']}: {what} [{e.get('source')}]")
    m = r["model"]
    lines += ["", "## Model", "", f"- Version: {m['model_version']}", f"- Hybrid trained on: {m['hybrid_trained_on']}",
              f"- Conformal level: {m['conformal_level']}; validated horizon: {m['validated_horizon_min']} min",
              f"- Calibration: {m['calibration']}"]
    lines += [f"- {n}" for n in m.get("notes", [])]
    return "\n".join(lines) + "\n"
