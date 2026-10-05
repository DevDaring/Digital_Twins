"""Agent template path (offline demo mode): edge-case wording, P(<70) caveat, grounding."""

from __future__ import annotations

import copy

import pytest

from pratifalan.agent import templates
from pratifalan.agent.orchestrator import Agent, rule_intent

LANGS = ("en-IN", "hi-IN", "bn-IN", "kn-IN")


class StubEngine:
    """Deterministic stand-in for TwinEngine with controllable outputs."""

    def __init__(self, narrowed: float = 0.4, gain: float = 23.4, p_low: float = 0.12,
                 wi: dict | None = None, contrib: float = 18.2) -> None:
        self.narrowed, self.gain, self.p_low, self.contrib = narrowed, gain, p_low, contrib
        self.wi = wi or {"delta_peak": -12.3, "p_high_change_small": False, "too_small_to_call": False,
                         "pb": 0.62, "ps": 0.41}
        self.fc = {"forecast_id": "f1", "peak": {"t": "2026-10-05T21:40", "value": 186.4},
                   "p_high": {"p": 0.32, "lo": 0.2, "hi": 0.45, "freq_text": "x"},
                   "p_low": {"p": p_low, "lo": 0.0, "hi": 0.3, "freq_text": "x", "validated": False},
                   "abstain": {"flag": False, "reason": None},
                   "drivers": [{"label_en": "Earlier food still digesting", "contribution": contrib}]}

    def state(self, pid, ladder, events, reveal=False, **kw):
        return {"estimate": 156.4, "band": {"lo": 131.2, "hi": 181.7}, "freshness": {"label": "fresh"},
                "forecast": copy.deepcopy(self.fc), "abstain": {"flag": False, "reason": None},
                "now": "2026-10-05T19:30"}

    def forecast(self, pid, ladder, events, meal=None, *a, **k):  # noqa: ANN002
        return copy.deepcopy(self.fc)

    def next_best_prick(self, pid, ladder, events, **kw):
        return {"time": "2026-10-05T21:40", "expected_gain_pct": self.gain, "reason": "r"}

    def assimilate(self, pid, ladder, events, value, **kw):
        self.assimilated = getattr(self, "assimilated", []) + [(float(value), kw)]
        return {"narrowed_pct": self.narrowed, "state": {"estimate": float(value)},
                "band_after": {"lo": 140.0, "hi": 170.0},
                "width_change": {"h120": {"signed_pct": -self.narrowed, "horizon_min": 120}}}

    def what_if(self, pid, ladder, events, base, scen, **kw):
        w = self.wi
        return {"baseline": {"peak": {"value": 190.0}, "p_high": {"p": w["pb"]}},
                "scenario": {"peak": {"value": 190.0 + w["delta_peak"]}, "p_high": {"p": w["ps"]}},
                "delta_peak": w["delta_peak"], "delta_p_high": {"mean": w["ps"] - w["pb"], "lo": -0.3, "hi": -0.1},
                "too_small_to_call": w["too_small_to_call"], "p_high_change_small": w["p_high_change_small"]}

    def explain(self, fid):
        return {"physiology": [{"label_en": "Earlier food still digesting", "contribution": self.contrib}],
                "learned": []}

    def outlook_90d(self, pid, ladder, events, **kw):
        return {"tir_current": [0.61], "tir_scenario": [0.7], "ehba1c_current": [7.4], "ehba1c_scenario": [7.0],
                "scenario_label": "s"}


def ask(text: str, lang: str = "en-IN", **stub) -> dict:
    return Agent(StubEngine(**stub)).handle(text, lang, "haripada", "2", [])


def confirm(r: dict, lang: str = "en-IN", ok: bool = True, **stub) -> tuple[dict, StubEngine]:
    eng = StubEngine(**stub)
    out = Agent(eng).confirm(r["pending_action"], ok, lang, "haripada", "2", [])
    return out, eng


@pytest.mark.parametrize("lang,text", [("en-IN", "my sugar is 150"), ("hi-IN", "मेरी शुगर 150 है"),
                                       ("bn-IN", "আমার সুগার 150"), ("kn-IN", "ನನ್ನ ಸಕ್ಕರೆ 150")])
def test_reading_is_proposed_then_confirmed(lang: str, text: str) -> None:
    eng = StubEngine(narrowed=0.4)
    r = Agent(eng).handle(text, lang, "haripada", "2", [])
    assert r["intent"] == "log_reading" and r["new_events"] == [] and not hasattr(eng, "assimilated")
    assert r["reply"] == templates.render("reading_offer", lang, value=150)
    pa = r["pending_action"]
    assert pa["kind"] == "log_reading" and pa["payload"]["value"] == 150.0 and pa["summary_en"]
    assert r["claims"] == [{"slot": "reading", "field": "log_reading.value", "value": 150.0, "rendered": "150"}]
    c, eng2 = confirm(r, lang, narrowed=0.4)
    assert c["reply"] == templates.render("reading_confirms", lang, value=150)
    assert " 0 " not in f" {c['reply']} " and c["grounding"]["passed"]
    assert c["new_events"] == [{"kind": "reading", "value": 150.0, "t_min": 0.0, "source": "chat"}]
    assert eng2.assimilated[0][0] == 150.0 and eng2.assimilated[0][1]["source"] == "chat"
    assert c["safety"]["level"] == "ok"


def test_confirmed_reading_reports_signed_percent() -> None:
    r = ask("my sugar is 150")
    c, _ = confirm(r, narrowed=31.6)
    assert "32 percent" in c["reply"] and "narrowed" in c["reply"] and c["grounding"]["passed"]
    c, _ = confirm(r, narrowed=-12.4)  # the band WIDENED: said honestly, not as "narrowed"
    assert "widened by 12 percent" in c["reply"] and c["grounding"]["passed"]
    assert {"slot": "pct", "field": "log_reading.width_change_h120_pct", "value": 12.4, "rendered": "12"} in c["claims"]


def test_cancel_and_stale_confirmation_do_not_mutate() -> None:
    r = ask("my sugar is 150")
    c, eng = confirm(r, ok=False)
    assert c["reply"] == templates.render("action_cancelled", "en-IN") and c.get("new_events", []) == []
    assert not hasattr(eng, "assimilated")
    eng = StubEngine()
    stale = Agent(eng).confirm(r["pending_action"], True, "en-IN", "haripada", "2", [], offset=45)
    assert stale["stale"] and stale.get("new_events", []) == [] and not hasattr(eng, "assimilated")


@pytest.mark.parametrize("lang", LANGS)
def test_low_carb_dish_wording(lang: str) -> None:
    r = ask("if i eat a boiled egg", lang)
    assert r["intent"] == "forecast"
    assert "grams" not in r["reply"] and "ग्राम" not in r["reply"]
    marker = {"en-IN": "very little carbohydrate", "hi-IN": "बहुत कम कार्ब्स", "bn-IN": "কার্বস খুবই কম",
              "kn-IN": "ಕಾರ್ಬ್ಸ್ ತುಂಬಾ ಕಡಿಮೆ"}[lang]
    assert marker in r["reply"]
    assert r["grounding"]["passed"]


@pytest.mark.parametrize("lang,text", [("en-IN", "how am i now"), ("hi-IN", "अभी मेरी शुगर कैसी है"),
                                       ("en-IN", "if i eat 2 roti and dal")])
def test_p_low_not_mentioned_unless_asked(lang: str, text: str) -> None:
    r = ask(text, lang)
    assert "70" not in r["reply"]
    for c in r["tool_calls"]:
        assert "p_low_2h" not in c["output"]


@pytest.mark.parametrize("lang,text,needle", [
    ("en-IN", "will my sugar go low tonight?", "not validated"),
    ("hi-IN", "क्या मेरी शुगर कम हो जाएगी?", "प्रमाणित नहीं"),
    ("bn-IN", "আমার সুগার কি কমে যাবে?", "যাচাই করা হয়নি"),
    ("kn-IN", "ನನ್ನ ಸಕ್ಕರೆ ಕಡಿಮೆ ಆಗುತ್ತದೆಯೇ?", "ಪರಿಶೀಲಿತವಲ್ಲ"),
])
def test_p_low_always_carries_not_validated(lang: str, text: str, needle: str) -> None:
    r = ask(text, lang)
    assert needle in r["reply"], r["reply"]
    outs = [c["output"] for c in r["tool_calls"] if "p_low_2h" in c["output"]]
    assert outs and all(o["p_low_2h"]["validated"] is False for o in outs)
    assert r["grounding"]["passed"]


def test_whatif_peak_only_when_probability_flat() -> None:
    r = ask("what if i walk 20 min after 2 roti", wi={"delta_peak": -12.0, "p_high_change_small": True,
                                                       "too_small_to_call": False, "pb": 0.86, "ps": 0.86})
    assert r["intent"] == "what_if"
    assert "stays about 86 percent" in r["reply"] and "from 86 to 86" not in r["reply"]


def test_whatif_peak_same_wording() -> None:
    r = ask("what if i walk after 2 roti", wi={"delta_peak": 0.3, "p_high_change_small": False,
                                                "too_small_to_call": False, "pb": 0.62, "ps": 0.55})
    assert "stays about the same" in r["reply"] and "+0" not in r["reply"]


def test_half_portion_is_the_scenario_not_the_base() -> None:
    a = Agent(StubEngine())
    r = a.handle("what if i eat half rice", "en-IN", "haripada", "2", [])
    args = next(c["args"] for c in r["tool_calls"] if c["name"] == "what_if")
    assert args["carb_scale"] == 0.5
    assert args["items"][0]["units"] == 1.0


def test_nbp_flat_and_explain_small() -> None:
    r = ask("when should i check next?", gain=0.4)
    assert "fairly sure" in r["reply"] and "0 percent" not in r["reply"]
    r = ask("why is it going up?", contrib=0.3)
    assert "No single factor" in r["reply"]


@pytest.mark.parametrize("lang", LANGS)
def test_dose_blocked_and_emergency(lang: str) -> None:
    dose = {"en-IN": "how much insulin should i take", "hi-IN": "इंसुलिन कितना लूँ",
            "bn-IN": "ইনসুলিন কতটা নেব", "kn-IN": "ಇನ್ಸುಲಿನ್ ಎಷ್ಟು ತೆಗೆದುಕೊಳ್ಳಲಿ"}[lang]
    r = ask(dose, lang)
    assert r["safety"]["blocked"] and not r["tool_calls"] and r["source"] == "fixture"
    emerg = {"en-IN": "my mother fainted", "hi-IN": "माँ बेहोश हो गईं", "bn-IN": "মা অজ্ঞান হয়ে গেছেন",
             "kn-IN": "ಅಮ್ಮ ಪ್ರಜ್ಞೆ ತಪ್ಪಿದ್ದಾರೆ"}[lang]
    r = ask(emerg, lang)
    assert r["safety"]["emergency"] and "108" in r["reply"]


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("text", ["how am i now", "if i eat 2 roti and dal", "when should i check next",
                                  "my sugar is 212", "what if i walk 15 min after 2 roti", "why",
                                  "what about the next 3 months", "what is time in range"])
def test_template_replies_are_grounded(lang: str, text: str) -> None:
    r = ask(text, lang)
    assert r["grounding"]["passed"], (r["reply"], r["grounding"])
    assert r["source"] == "fixture" and r["source_detail"] == "template"


def test_rule_router_indic() -> None:
    assert rule_intent("अगर मैं अभी चावल और दाल खाऊँ तो क्या होगा?")[0] == "forecast"
    assert rule_intent("ನಾನು ಈಗ ರಾಗಿ ಮುದ್ದೆ ಮತ್ತು ಸಾರು ತಿಂದರೆ ಏನಾಗುತ್ತದೆ?")[0] == "forecast"
    assert rule_intent("কখন মাপব?")[0] == "next_prick"


@pytest.mark.parametrize("lang", LANGS)
def test_clock_uses_day_parts(lang: str) -> None:
    out = templates.clock("2026-10-05T21:40", lang)
    assert "9:40" in out
    if lang != "en-IN":
        assert "am" not in out and "pm" not in out


# ----------------------------------------------------------------------------- safety before routing
@pytest.mark.parametrize("lang,text,value", [("en-IN", "my sugar is 48", 48), ("hi-IN", "शुगर 62 है और हाथ काँप रहे हैं", 62),
                                             ("bn-IN", "সুগার 450, বমি হচ্ছে", 450), ("kn-IN", "ಎದೆಯಲ್ಲಿ ತುಂಬಾ ನೋವು", None)])
def test_emergency_before_any_routing_or_logging(lang: str, text: str, value: int | None) -> None:
    eng = StubEngine()
    r = Agent(eng).handle(text, lang, "haripada", "2", [])
    assert r["safety"]["emergency"] and r["intent"] == "emergency" and "108" in r["reply"]
    assert r["new_events"] == [] and not hasattr(eng, "assimilated")  # nothing is stored without confirmation
    if value is None:
        assert r["tool_calls"] == [] and r["pending_action"] is None
    else:  # the reported reading is only PROPOSED for logging, after the emergency message
        assert [c["name"] for c in r["tool_calls"]] == ["log_reading"]
        assert r["pending_action"]["payload"]["value"] == float(value)
        assert r["safety"]["assessment"]["emergency"] is True


@pytest.mark.parametrize("lang,text,kind,value", [
    ("en-IN", "my sugar is 65", "hypo", 65), ("hi-IN", "मेरी शुगर 64 आई है", "hypo", 64),
    ("bn-IN", "আমার সুগার ৩৪০", "hyper", 340), ("kn-IN", "ನನ್ನ ಸಕ್ಕರೆ 320 ಬಂದಿದೆ", "hyper", 320),
    ("en-IN", "my sugar is 270", "high", 270),
])
def test_low_or_high_reading_always_gets_safety_message(lang: str, text: str, kind: str, value: int) -> None:
    r = ask(text, lang, narrowed=0.2)
    from pratifalan.agent import safety

    a = safety.assess_reading(value, text, lang)
    assert r["reply"].startswith(safety.message(kind, lang, value=value)) and r["reply"].startswith(a["message"])
    assert r["safety"]["reason"] == a["reason"] and r["safety"]["level"] == a["level"] and r["grounding"]["passed"]
    assert templates.render("reading_confirms", lang, value=value) not in r["reply"]  # no reassurance
    assert safety.message("reading_pending", lang) in r["reply"]
    assert r["new_events"] == [] and r["pending_action"]["payload"]["value"] == float(value)
    c, _ = confirm(r, lang)  # confirming goes through the same policy: same message, then "added"
    assert c["reply"].startswith(a["message"]) and c["safety"]["level"] == a["level"]
    assert c["new_events"][0]["value"] == float(value)


def test_hypothetical_low_value_is_not_logged() -> None:
    r = ask("what happens if my sugar is 65?")
    assert r["safety"]["reason"] == "low_reading" and r["new_events"] == [] and r["pending_action"] is None


@pytest.mark.parametrize("lang,text", [("en-IN", "Who won the IPL final this year?"),
                                       ("en-IN", "How do I make chicken biryani?"),
                                       ("hi-IN", "कल लखनऊ में मौसम कैसा रहेगा?"), ("hi-IN", "कोई अच्छी सी कहानी सुनाओ।"),
                                       ("bn-IN", "আজ মোহনবাগানের খেলার স্কোর কত?"),
                                       ("kn-IN", "ಮೈಸೂರು ದಸರಾ ಜಂಬೂ ಸವಾರಿ ಯಾವ ದಿನ?")])
def test_out_of_scope_rules(lang: str, text: str) -> None:
    from pratifalan.agent import safety

    r = ask(text, lang)
    assert r["intent"] == "out_of_scope" and r["reply"] == safety.message("out_of_scope", lang)


@pytest.mark.parametrize("text,intent", [
    ("Can I eat biryani while watching the cricket match?", "forecast"),
    ("what's the weather like for my sugar after a walk?", "what_if"),
    ("great, thanks", "state"),                       # 'eat' inside 'great' is not food
    ("मेरी शुगर अभी 172 आई है।", "log_reading"),
    ("আমার সুগার এইমাত্র ১৬৫ এল।", "log_reading"),
    ("sugar 158 now", "log_reading"),
    ("এখন এক থালা ভাত আর মাছের ঝোল খাই, সুগার কতটা বাড়বে?", "forecast"),
    ("ಬೆಳಿಗ್ಗೆ 2 ಮಸಾಲೆ ದೋಸೆ ಮತ್ತು ಫಿಲ್ಟರ್ ಕಾಫಿ ತಗೊಂಡರೆ ಏನಾಗುತ್ತದೆ?", "forecast"),
    ("अगर मैं चावल की जगह 2 रोटी खाऊँ तो क्या फ़र्क पड़ेगा?", "what_if"),
    ("अगर खिचड़ी आधी प्लेट ही खाऊँ तो?", "what_if"),
    ("ভাতের বদলে দুটো রুটি খেলে কতটা তফাত হবে?", "what_if"),
    ("ಅನ್ನದ ಬದಲು ಎರಡು ಚಪಾತಿ ತಿಂದರೆ ಎಷ್ಟು ವ್ಯತ್ಯಾಸ ಆಗುತ್ತದೆ?", "what_if"),
])
def test_router_rules(text: str, intent: str) -> None:
    assert rule_intent(text)[0] == intent


def test_table_sugar_needs_a_quantity() -> None:
    from pratifalan.agent.orchestrator import parse_foods

    assert parse_foods("my sugar is high today") == []
    assert parse_foods("2 spoon sugar in tea")[0]["food_id"] == "sugar_tsp"


def _whatif_args(text: str, lang: str = "en-IN") -> dict:
    r = Agent(StubEngine()).handle(text, lang, "haripada", "2", [])
    return next(c["args"] for c in r["tool_calls"] if c["name"] == "what_if")


@pytest.mark.parametrize("text,lang,base,scen", [
    ("What if I eat 2 rotis instead of a katori of rice with my dal?", "en-IN",
     [("dal_toor_katori", 1.0), ("white_rice_katori", 1.0)], [("dal_toor_katori", 1.0), ("roti_piece", 2.0)]),
    ("अगर मैं चावल की जगह 2 रोटी खाऊँ तो क्या फ़र्क पड़ेगा?", "hi-IN",
     [("white_rice_katori", 1.0)], [("roti_piece", 2.0)]),
    ("ভাতের বদলে দুটো রুটি খেলে কতটা তফাত হবে?", "bn-IN", [("white_rice_katori", 1.0)], [("roti_piece", 2.0)]),
    ("ಅನ್ನದ ಬದಲು ಎರಡು ಚಪಾತಿ ತಿಂದರೆ ಎಷ್ಟು ವ್ಯತ್ಯಾಸ ಆಗುತ್ತದೆ?", "kn-IN", [("white_rice_katori", 1.0)],
     [("roti_piece", 2.0)]),
    ("what if I swap rice for ragi mudde", "en-IN", [("white_rice_katori", 1.0)], [("ragi_mudde_piece", 1.0)]),
    ("what if I eat brown rice instead of rice", "en-IN", [("white_rice_katori", 1.0)], [("brown_rice_katori", 1.0)]),
    ("what if I have millet instead of rice", "en-IN", [("white_rice_katori", 1.0)], [("bajra_roti_piece", 1.0)]),
])
def test_swap_baseline_is_replaced_food_scenario_is_replacement(text, lang, base, scen) -> None:
    a = _whatif_args(text, lang)
    assert [(i["food_id"], i["units"]) for i in a["items"]] == base
    assert [(i["food_id"], i["units"]) for i in a["swap_items"]] == scen
    assert "walk_min" not in a


def test_half_applies_to_the_named_dish_only() -> None:
    a = _whatif_args("আজ রাতে ভাত অর্ধেক করে খেলে কী হবে? সঙ্গে ডাল আর মাছের ঝোল।", "bn-IN")
    rice = [i for i in a["swap_items"] if i["food_id"] == "white_rice_katori"]
    assert rice[0]["units"] == 0.5 and all(i["units"] == 1.0 for i in a["items"])


@pytest.mark.parametrize("lang", LANGS)
def test_unidentified_change_says_so_instead_of_a_walk(lang: str) -> None:
    text = {"en-IN": "what if I have something else instead of rice", "hi-IN": "अगर चावल की जगह कुछ और खाऊँ तो?",
            "bn-IN": "ভাতের বদলে অন্য কিছু খেলে কী হবে?", "kn-IN": "ಅನ್ನದ ಬದಲು ಬೇರೆ ಏನಾದರೂ ತಿಂದರೆ ಏನಾಗುತ್ತದೆ?"}[lang]
    r = ask(text, lang)
    assert r["reply"] == templates.render("whatif_unknown", lang)
    assert not any(c["name"] == "what_if" for c in r["tool_calls"])


@pytest.mark.parametrize("lang,needle", [("en-IN", "earlier food still digesting"),
                                         ("hi-IN", "पहले खाया खाना"), ("bn-IN", "আগের খাবার"),
                                         ("kn-IN", "ಮೊದಲು ತಿಂದ ಆಹಾರ")])
def test_driver_labels_localised(lang: str, needle: str) -> None:
    r = ask({"en-IN": "why is it going up?", "hi-IN": "शुगर क्यों बढ़ेगी?", "bn-IN": "সুগার কেন বাড়বে?",
             "kn-IN": "ಸಕ್ಕರೆ ಯಾಕೆ ಏರುತ್ತದೆ?"}[lang], lang)
    assert needle in r["reply"] and "Earlier food" not in r["reply"]


def test_dish_names_are_tts_friendly() -> None:
    r = ask("if i eat 2 roti and dal")
    assert "/" not in r["reply"] and "(" not in r["reply"]
    assert "2 roti and toor dal" in r["reply"]


def test_highlight_window_from_forecast() -> None:
    eng = StubEngine()
    eng.fc["origin"] = "2026-10-05T19:30"
    r = Agent(eng).handle("if i eat 2 roti and dal", "en-IN", "haripada", "2", [])
    assert r["highlight"] == {"view": "forecast", "from": "2026-10-05T19:30", "to": "2026-10-05T21:40"}


# ----------------------------------------------------------------------------- live path (LLM mocked)
class FakeLLM:
    """Scripted LLMClient: router JSON answers and planner drafts."""

    def __init__(self, route: dict | None, drafts: list[str]) -> None:
        self.route, self.drafts, self.planner_calls = route, list(drafts), 0

    def json(self, role, messages, **kw):
        from pratifalan.providers.llm import LLMResult, LLMUnavailable

        if self.route is None:
            raise LLMUnavailable("down")
        return self.route, LLMResult("", [], "openrouter", "test-router", 1, {})

    def chat(self, role, messages, tools=None, **kw):
        from pratifalan.providers.llm import LLMResult

        self.planner_calls += 1
        if tools and self.planner_calls == 1:
            return LLMResult("", [{"id": "c1", "name": "get_state", "args": {}}], "openrouter", "test-planner", 1, {})
        return LLMResult(self.drafts.pop(0) if self.drafts else "", [], "openrouter", "test-planner", 1, {})


def _live_agent(monkeypatch, route: dict | None, drafts: list[str]) -> Agent:
    import pratifalan.agent.orchestrator as O

    monkeypatch.setattr(O, "available", lambda role: True)
    a = Agent(StubEngine())
    a.llm = FakeLLM(route, drafts)  # type: ignore[assignment]
    return a


@pytest.mark.parametrize("label,flag", [("dose", "blocked"), ("emergency", "emergency")])
def test_llm_safety_label_is_authoritative(monkeypatch, label: str, flag: str) -> None:
    a = _live_agent(monkeypatch, {"intent": "state", "safety": label}, ["Your sugar is about {estimate}."])
    r = a.handle("something the rules do not catch", "en-IN", "haripada", "2", [])
    assert r["safety"][flag] and r["source"] == "live" and r["source_detail"].startswith("router")
    assert r["tool_calls"] == []


def test_rules_win_even_when_llm_says_none(monkeypatch) -> None:
    a = _live_agent(monkeypatch, {"intent": "state", "safety": "none"}, [])
    r = a.handle("How many units of insulin should I take?", "en-IN", "haripada", "2", [])
    assert r["safety"]["blocked"] and r["source_detail"] == "rules"


def test_live_draft_cut_off_is_regenerated_then_used(monkeypatch) -> None:
    a = _live_agent(monkeypatch, {"intent": "state", "safety": "none"},
                    ["Right now your glucose is about {estimate} and", "Right now your glucose is about {estimate}."])
    r = a.handle("how am i now", "en-IN", "haripada", "2", [])
    assert r["reply"] == "Right now your glucose is about 156." and r["source"] == "live"
    assert r["source_detail"] == "openrouter:test-planner" and not r["grounding"]["fallback_used"]
    assert r["claims"] == [{"slot": "estimate", "field": "get_state.estimate", "value": 156.4, "rendered": "156"}]


def test_live_raw_digits_are_rejected_then_slot_draft_used(monkeypatch) -> None:
    a = _live_agent(monkeypatch, {"intent": "state", "safety": "none"},
                    ["Right now your glucose is about 156.", "Your {risk_high}."])
    r = a.handle("how am i now", "en-IN", "haripada", "2", [])
    assert r["reply"] == "Your chance of going above 180 in the next 2 hours: about 3 times out of 10."
    assert r["claims"][0]["field"] == "get_state.p_high_2h.p" and r["claims"][0]["value"] == 0.32


def test_live_unknown_slot_and_digits_fall_back_to_template(monkeypatch) -> None:
    a = _live_agent(monkeypatch, {"intent": "state", "safety": "none"},
                    ["Your peak is {peak}.", "Your low glucose risk is 80%."])
    r = a.handle("how am i now", "en-IN", "haripada", "2", [])
    assert r["grounding"]["fallback_used"] and r["source_detail"].startswith("template fallback after")
    assert "80%" not in r["reply"] and "low glucose risk" not in r["reply"]


def test_live_user_numbers_may_be_repeated(monkeypatch) -> None:
    a = _live_agent(monkeypatch, {"intent": "state", "safety": "none"},
                    ["You asked about 200; right now you are about {estimate}."])
    r = a.handle("will I go above 200 now?", "en-IN", "haripada", "2", [])
    assert r["reply"] == "You asked about 200; right now you are about 156." and not r["grounding"]["fallback_used"]


def test_live_medication_mention_falls_back(monkeypatch) -> None:
    a = _live_agent(monkeypatch, {"intent": "state", "safety": "none"},
                    ["Keep taking your metformin; you are about {estimate}.", "Skip your goli tonight."])
    r = a.handle("how am i now", "en-IN", "haripada", "2", [])
    assert r["grounding"]["fallback_used"] and "metformin" not in r["reply"].lower()


def test_live_bad_drafts_fall_back_to_template(monkeypatch) -> None:
    a = _live_agent(monkeypatch, {"intent": "state", "safety": "none"}, ["Peak {estimate}:", "Your sugar is {estimate} now."])
    r = a.handle("अभी मेरी शुगर कैसी है?", "hi-IN", "haripada", "2", [])
    assert r["grounding"]["fallback_used"] and r["source"] == "live"
    assert r["source_detail"].startswith("template fallback after")
    assert "156" in r["reply"] and "अभी" in r["reply"]


def test_live_router_down_still_works(monkeypatch) -> None:
    a = _live_agent(monkeypatch, None, ["Right now your glucose is about {estimate}."])
    r = a.handle("how am i now", "en-IN", "haripada", "2", [])
    assert r["reply"] == "Right now your glucose is about 156."


def test_live_logged_low_value_gets_hypo_message(monkeypatch) -> None:
    """Even if the planner logs a low value the rules did not see, the reply is the hypo message."""
    a = _live_agent(monkeypatch, {"intent": "log_reading", "safety": "none"}, ["Thanks, noted."])
    a.llm.chat = lambda role, messages, tools=None, **kw: (  # type: ignore[method-assign]
        __import__("pratifalan.providers.llm", fromlist=["LLMResult"]).LLMResult(
            "", [{"id": "c1", "name": "log_reading", "args": {"value": 62}}], "p", "m", 1, {})
        if tools and not any(m.get("role") == "tool" for m in messages)
        else __import__("pratifalan.providers.llm", fromlist=["LLMResult"]).LLMResult("Thanks, noted.", [], "p", "m", 1, {}))
    r = a.handle("I checked, it was sixty two", "en-IN", "haripada", "2", [])
    from pratifalan.agent import safety

    assert r["reply"].startswith(safety.message("hypo", "en-IN", value=62))
    assert r["pending_action"]["kind"] == "log_reading" and r["new_events"] == []
