"""Deterministic slot rendering (contract v3, C8).

The live planner never writes numbers. It writes text with slots such as ``{estimate}`` or
``{risk_high}``; each slot is bound to ONE tool field of this turn and rendered here, in the
user's language, by code. A slot whose tool was not called is rejected, and so is any raw
digit in the draft that the user did not type. Templates use the same ``Slot`` objects, so
every reply carries ``claims``: ``[{slot, field, value, rendered}]``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pratifalan.agent import templates as T
from pratifalan.agent.verifier import extract_numbers, normalise_digits

SLOT_RE = re.compile(r"\{([a-z][a-z0-9_]*)\}")
DIGIT_RE = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass
class Slot:
    name: str
    field: str
    value: Any
    rendered: str

    def claim(self) -> dict:
        v = self.value
        if isinstance(v, float):
            v = round(v, 3)
        return {"slot": self.name, "field": self.field, "value": v, "rendered": self.rendered}


RISK_HIGH = {
    "en-IN": "chance of going above 180 in the next 2 hours: {freq}",
    "hi-IN": "अगले 2 घंटों में 180 से ऊपर जाने की संभावना: {freq}",
    "bn-IN": "পরের 2 ঘণ্টায় 180-এর ওপরে যাওয়ার সম্ভাবনা: {freq}",
    "kn-IN": "ಮುಂದಿನ 2 ಗಂಟೆಗಳಲ್ಲಿ 180 ಮೀರುವ ಸಾಧ್ಯತೆ: {freq}",
}
RISK_LOW = {
    "en-IN": "estimated chance of going below 70 in the next 2 hours (not validated): {freq}",
    "hi-IN": "अगले 2 घंटों में 70 से नीचे जाने का अनुमान (प्रमाणित नहीं): {freq}",
    "bn-IN": "পরের 2 ঘণ্টায় 70-এর নিচে নামার অনুমান (যাচাই করা হয়নি): {freq}",
    "kn-IN": "ಮುಂದಿನ 2 ಗಂಟೆಗಳಲ್ಲಿ 70 ಕ್ಕಿಂತ ಕೆಳಗೆ ಹೋಗುವ ಅಂದಾಜು (ಪರಿಶೀಲಿತವಲ್ಲ): {freq}",
}
RANGE = {"en-IN": "{lo} to {hi}", "hi-IN": "{lo} से {hi}", "bn-IN": "{lo} থেকে {hi}", "kn-IN": "{lo} ರಿಂದ {hi}"}
WALK_EFFECT = {
    "down": {"en-IN": "lowers the expected peak by about {n}", "hi-IN": "अनुमानित उच्चतम स्तर लगभग {n} कम करता है",
             "bn-IN": "আনুমানিক সর্বোচ্চ মাত্রা প্রায় {n} কমায়", "kn-IN": "ಅಂದಾಜು ಗರಿಷ್ಠ ಮಟ್ಟವನ್ನು ಸುಮಾರು {n} ಕಡಿಮೆ ಮಾಡುತ್ತದೆ"},
    "up": {"en-IN": "raises the expected peak by about {n}", "hi-IN": "अनुमानित उच्चतम स्तर लगभग {n} बढ़ाता है",
           "bn-IN": "আনুমানিক সর্বোচ্চ মাত্রা প্রায় {n} বাড়ায়", "kn-IN": "ಅಂದಾಜು ಗರಿಷ್ಠ ಮಟ್ಟವನ್ನು ಸುಮಾರು {n} ಹೆಚ್ಚಿಸುತ್ತದೆ"},
    "small": {"en-IN": "changes the expected peak too little to call",
              "hi-IN": "अनुमानित उच्चतम स्तर को इतना कम बदलता है कि पक्का नहीं कह सकते",
              "bn-IN": "আনুমানিক সর্বোচ্চ মাত্রা এত কম বদলায় যে নিশ্চিত বলা যায় না",
              "kn-IN": "ಅಂದಾಜು ಗರಿಷ್ಠ ಮಟ್ಟವನ್ನು ಖಚಿತವಾಗಿ ಹೇಳಲಾಗದಷ್ಟು ಕಡಿಮೆ ಬದಲಿಸುತ್ತದೆ"},
}

# Slot catalogue shown to the planner: name -> (tool, field, meaning).
CATALOGUE: dict[str, tuple[str, str, str]] = {
    "estimate": ("get_state", "estimate", "current glucose estimate (mg/dL)"),
    "band": ("get_state", "band", "likely range of current glucose, e.g. '131 to 182'"),
    "risk_high": ("get_state|forecast", "p_high_2h.p", "full phrase: chance of going above 180 in the next 2 hours"),
    "risk_low": ("get_state|forecast", "p_low_2h.p", "full phrase incl. 'not validated': chance below 70 (only if asked)"),
    "peak": ("forecast", "peak.value", "expected peak glucose of the forecast"),
    "peak_time": ("forecast", "peak.t", "clock time of that peak"),
    "carbs": ("forecast", "meal.carbs", "grams of carbohydrate in the meal"),
    "meal": ("forecast", "meal.name", "the meal's name"),
    "delta_peak": ("what_if", "delta_peak", "signed change of the peak in the simulated scenario, e.g. '-12'"),
    "walk_effect": ("what_if", "delta_peak", "phrase: what the simulated walk does to the peak"),
    "risk_high_before": ("what_if", "p_high_baseline", "percent chance above 180 without the change"),
    "risk_high_after": ("what_if", "p_high_scenario", "percent chance above 180 with the change"),
    "next_check": ("next_best_prick", "time", "suggested time for the next finger-prick (experimental)"),
    "nbp_gain": ("next_best_prick", "expected_gain_pct", "percent the twin's uncertainty may shrink"),
    "reading": ("log_reading", "value", "the reading the user reported"),
    "driver": ("explain", "physiology[0].label", "the biggest driver, in words"),
    "driver_effect": ("explain", "physiology[0].effect_on_peak", "signed effect of that driver on the peak"),
    "tir_current": ("outlook_90d", "tir_current_pct", "projected time in range, current habits (percent)"),
    "tir_scenario": ("outlook_90d", "tir_scenario_pct", "projected time in range with the change (percent)"),
    "target_range": ("constant", "target", "the target range '70 to 180'"),
    "emergency_number": ("constant", "108", "India's ambulance number"),
}


def _lang(d: dict[str, str], lang: str) -> str:
    return d.get(lang, d["en-IN"])


def risk_phrase(p: float, lang: str, low: bool = False) -> str:
    return _lang(RISK_LOW if low else RISK_HIGH, lang).format(freq=T.freq(p, lang))


def range_phrase(lo: float, hi: float, lang: str) -> str:
    return _lang(RANGE, lang).format(lo=round(lo), hi=round(hi))


def build(calls: list[dict], lang: str) -> dict[str, Slot]:
    """Slots available from this turn's tool calls (the most recent call wins)."""
    s: dict[str, Slot] = {
        "target_range": Slot("target_range", "constant.target", [70, 180], range_phrase(70, 180, lang)),
        "emergency_number": Slot("emergency_number", "constant.emergency_number", 108, "108"),
    }
    for c in calls:
        name, o = c.get("name"), c.get("output") or {}
        if not isinstance(o, dict) or "error" in o:
            continue
        if name == "get_state":
            s["estimate"] = Slot("estimate", "get_state.estimate", o["estimate"], str(round(o["estimate"])))
            b = o["band"]
            s["band"] = Slot("band", "get_state.band", [b["lo"], b["hi"]], range_phrase(b["lo"], b["hi"], lang))
        if name in ("get_state", "forecast", "log_meal") and isinstance(o.get("p_high_2h"), dict):
            p = float(o["p_high_2h"]["p"])
            s["risk_high"] = Slot("risk_high", f"{name}.p_high_2h.p", p, risk_phrase(p, lang))
        if name in ("get_state", "forecast") and isinstance(o.get("p_low_2h"), dict):
            p = float(o["p_low_2h"]["p"])
            s["risk_low"] = Slot("risk_low", f"{name}.p_low_2h.p", p, risk_phrase(p, lang, low=True))
        if name in ("forecast", "log_meal") and isinstance(o.get("peak"), dict):
            s["peak"] = Slot("peak", f"{name}.peak.value", o["peak"]["value"], str(round(o["peak"]["value"])))
            s["peak_time"] = Slot("peak_time", f"{name}.peak.t", o["peak"]["t"], T.clock(o["peak"]["t"], lang))
            meal = o.get("meal") or {}
            if meal:
                s["carbs"] = Slot("carbs", f"{name}.meal.carbs", meal.get("carbs"), str(round(float(meal.get("carbs") or 0))))
                s["meal"] = Slot("meal", f"{name}.meal.name", meal.get("name"), str(meal.get("name") or ""))
        if name == "what_if":
            dp = float(o["delta_peak"])
            s["delta_peak"] = Slot("delta_peak", "what_if.delta_peak", dp, T.signed(dp))
            kind = "small" if o.get("too_small_to_call") or abs(round(dp)) < 1 else ("down" if dp < 0 else "up")
            s["walk_effect"] = Slot("walk_effect", "what_if.delta_peak", dp,
                                    WALK_EFFECT[kind].get(lang, WALK_EFFECT[kind]["en-IN"]).format(n=abs(round(dp))))
            s["risk_high_before"] = Slot("risk_high_before", "what_if.p_high_baseline", o["p_high_baseline"],
                                         str(round(float(o["p_high_baseline"]) * 100)))
            s["risk_high_after"] = Slot("risk_high_after", "what_if.p_high_scenario", o["p_high_scenario"],
                                        str(round(float(o["p_high_scenario"]) * 100)))
        if name == "next_best_prick" and o.get("time"):
            s["next_check"] = Slot("next_check", "next_best_prick.time", o["time"], T.clock(o["time"], lang))
            s["nbp_gain"] = Slot("nbp_gain", "next_best_prick.expected_gain_pct", o["expected_gain_pct"],
                                 str(round(float(o["expected_gain_pct"]))))
        if name == "log_reading" and o.get("value") is not None:
            s["reading"] = Slot("reading", "log_reading.value", o["value"], str(round(float(o["value"]))))
        if name == "explain" and o.get("physiology"):
            top = o["physiology"][0]
            s["driver"] = Slot("driver", "explain.physiology[0].label", top["label"],
                               T.driver_label(top.get("name"), top["label"], lang))
            s["driver_effect"] = Slot("driver_effect", "explain.physiology[0].effect_on_peak", top["effect_on_peak"],
                                      T.signed(top["effect_on_peak"]))
        if name == "outlook_90d":
            s["tir_current"] = Slot("tir_current", "outlook_90d.tir_current_pct", o["tir_current_pct"],
                                    str(o["tir_current_pct"]))
            s["tir_scenario"] = Slot("tir_scenario", "outlook_90d.tir_scenario_pct", o["tir_scenario_pct"],
                                     str(o["tir_scenario_pct"]))
    return s


def raw_digits(draft: str, user_text: str) -> list[str]:
    """Digits the planner wrote itself (slots removed) that are not the user's own numbers."""
    body = SLOT_RE.sub(" ", normalise_digits(draft))
    mine = set(extract_numbers(user_text))
    out = []
    for m in DIGIT_RE.finditer(body):
        try:
            v = float(m.group(0).replace(",", "."))
        except ValueError:
            continue
        if v not in mine:
            out.append(m.group(0))
    return out


def render(draft: str, slots: dict[str, Slot]) -> tuple[str, list[dict], list[str]]:
    """Fill ``{slot}`` placeholders. Returns (text, claims, unknown slot names)."""
    claims: list[dict] = []
    unknown: list[str] = []

    def sub(m: re.Match[str]) -> str:
        name = m.group(1)
        sl = slots.get(name)
        if sl is None:
            unknown.append(name)
            return m.group(0)
        claims.append(sl.claim())
        return sl.rendered

    return SLOT_RE.sub(sub, draft), claims, unknown


def catalogue_text(slots: dict[str, Slot] | None = None) -> str:
    names = list(CATALOGUE) if slots is None else [n for n in CATALOGUE if n in slots]
    return "\n".join(f"{{{n}}}: {CATALOGUE[n][2]} (from {CATALOGUE[n][0]})" for n in names)
