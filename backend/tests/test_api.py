"""REST API end-to-end (FastAPI TestClient against the pratifalan_test database)."""

from __future__ import annotations

import math

import pytest

PID = "haripada"
MEAL = {"name": "rice and dal", "carbs": 55.5, "fibre": 3.0, "protein": 12.0, "fat": 6.0,
        "items": [{"food_id": "white_rice_katori", "units": 1}, {"food_id": "dal_toor_katori", "units": 1}]}
SECTION_46 = [
    ("get", "/api/twin/{pid}/state"), ("post", "/api/twin/{pid}/forecast"), ("post", "/api/twin/{pid}/what_if"),
    ("get", "/api/twin/{pid}/next_best_prick"), ("post", "/api/twin/{pid}/assimilate"),
    ("get", "/api/twin/{pid}/outlook_90d"), ("get", "/api/twin/{pid}/explain/{forecast_id}"),
]


def _no_nan(o) -> bool:
    if isinstance(o, float):
        return math.isfinite(o)
    if isinstance(o, dict):
        return all(_no_nan(v) for v in o.values())
    if isinstance(o, list):
        return all(_no_nan(v) for v in o)
    return True


@pytest.fixture(autouse=True, scope="module")
def _clean_twin(client, auth):
    client.post(f"/api/twin/{PID}/reset", headers=auth)
    yield
    client.post(f"/api/twin/{PID}/reset", headers=auth)


# ----------------------------------------------------------------------------- auth / health
def test_health(client) -> None:
    assert client.get("/api/health").json() == {"ok": True, "mode": "demo"}


def test_login_ok_and_me(client, auth) -> None:
    r = client.post("/api/auth/login", json={"username": "TestUser", "password": "TestUser11"})
    assert r.status_code == 200 and r.json()["user"]["username"] == "TestUser"
    me = client.get("/api/auth/me", headers=auth).json()
    assert me["username"] == "DevTester" and set(me["roles"]) <= {"patient", "clinician"}


@pytest.mark.parametrize("u,p", [("DevTester", "wrong"), ("nobody", "DevTester11"), ("DevTester", "")])
def test_login_fail(client, u: str, p: str) -> None:
    r = client.post("/api/auth/login", json={"username": u, "password": p})
    assert r.status_code == 401 and "detail" in r.json()


@pytest.mark.parametrize("path", ["/api/auth/me", "/api/patients", f"/api/twin/{PID}/state",
                                  f"/api/twin/{PID}/next_best_prick", "/api/reports"])
def test_401_without_token(client, path: str) -> None:
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer not-a-token"}).status_code == 401


# ----------------------------------------------------------------------------- patients
def test_patients(client, auth) -> None:
    ps = client.get("/api/patients", headers=auth).json()
    assert {p["id"] for p in ps} == {"haripada", "lakshmi", "ramesh"}
    for p in ps:
        assert p["synthetic"] is True and p["sex"] in ("F", "M") and len(p["sparkline"]) > 0
        assert 0 <= p["tir_7d"] <= 1 and 0 <= p["risk_7d"] <= 1
    d = client.get(f"/api/patients/{PID}", headers=auth).json()
    assert d["ehr"]["medications"] and d["calibration"]["cgm_days"] == 5.0
    assert client.get("/api/patients/nobody", headers=auth).status_code == 404


# ----------------------------------------------------------------------------- twin (Section 4.6)
def test_state(client, auth) -> None:
    r = client.get(f"/api/twin/{PID}/state", params={"ladder": "2"}, headers=auth)
    assert r.status_code == 200
    s = r.json()
    for k in ("now", "ladder", "estimate", "band", "freshness", "last_observation", "abstain", "ess", "history",
              "forecast", "next_best_prick", "target"):
        assert k in s, k
    assert s["p_low_validated"] is False and s["forecast"]["p_low_validated"] is False
    assert s["ladder"] == "2" and s["target"] == {"lo": 70, "hi": 180}
    assert "true_cgm" not in s["history"]
    assert _no_nan(s)
    rv = client.get(f"/api/twin/{PID}/state", params={"ladder": "2", "reveal": 1}, headers=auth).json()
    assert rv["history"]["true_cgm"]["v"]


def test_forecast_with_meal_and_explain(client, auth) -> None:
    r = client.post(f"/api/twin/{PID}/forecast", json={"ladder": "2", "meal": MEAL}, headers=auth)
    assert r.status_code == 200
    fc = r.json()
    assert fc["conformal_level"] == 0.9 and fc["horizon_min"] == 240 and len(fc["traj"]["t"]) == 48
    assert fc["p_low"]["validated"] is False and fc["p_low_validated"] is False
    assert {"p", "freq_text", "validated", "reliability"} <= set(fc["p_high"]) and fc["p_high"]["validated"] is True
    assert "lo" not in fc["p_high"] and "hi" not in fc["p_high"]  # no particle-binomial interval (v3)
    assert fc["traj"]["validated_horizon_min"] == 120 and fc["provenance"]["observations_used"] > 0
    assert fc["drivers"] and all(d["source"] in ("physiology", "learned") for d in fc["drivers"])
    ex = client.get(f"/api/twin/{PID}/explain/{fc['forecast_id']}", headers=auth)
    assert ex.status_code == 200
    ex = ex.json()
    assert ex["physiology"] and all(d["source"] == "physiology" for d in ex["physiology"])
    assert all(d["source"] == "learned" for d in ex["learned"])
    assert client.get(f"/api/twin/{PID}/explain/doesnotexist", headers=auth).status_code == 404


def test_forecast_short_horizon(client, auth) -> None:
    fc = client.post(f"/api/twin/{PID}/forecast", json={"ladder": "2", "horizon_min": 60}, headers=auth).json()
    assert fc["horizon_min"] == 60 and len(fc["traj"]["q50"]) == 12


def test_what_if_with_swap(client, auth) -> None:
    body = {"ladder": "2", "base_meal": MEAL,
            "scenario": {"swap": {"from": "white_rice_katori", "to": "roti_piece"}, "walk_min": 15}}
    r = client.post(f"/api/twin/{PID}/what_if", json=body, headers=auth)
    assert r.status_code == 200, r.text
    w = r.json()
    assert {"baseline", "scenario", "delta_p_high", "delta_peak", "too_small_to_call", "note"} <= set(w)
    assert w["delta_p_high"]["lo"] <= w["delta_p_high"]["mean"] <= w["delta_p_high"]["hi"]
    assert w["delta_peak"] <= 0  # rice -> roti plus a walk never raises the peak
    assert w["scenario"]["p_low_validated"] is False
    bad = {"ladder": "2", "base_meal": MEAL, "scenario": {"swap": {"from": "white_rice_katori", "to": "pizza"}}}
    assert client.post(f"/api/twin/{PID}/what_if", json=bad, headers=auth).status_code == 422


def test_next_best_prick(client, auth) -> None:
    nb = client.get(f"/api/twin/{PID}/next_best_prick", params={"ladder": "2"}, headers=auth).json()
    assert nb["time"] and nb["reason"] and nb["candidates"]
    assert all({"t", "gain_pct"} <= set(c) for c in nb["candidates"])


def test_prick_at_the_estimate_reports_the_band_change_honestly(client, auth) -> None:
    """A reading equal to the estimate may narrow OR widen the band (after a 12.5 h gap the filter
    inflates its spread before the update). v3 reports the signed change instead of promising narrowing;
    the before/after numbers are exactly the bands the UI animates."""
    client.post(f"/api/twin/{PID}/reset", headers=auth)
    before = client.get(f"/api/twin/{PID}/state", params={"ladder": "2"}, headers=auth).json()
    a = client.post(f"/api/twin/{PID}/assimilate", json={"ladder": "2", "value": before["estimate"], "unit": "mg/dL"},
                    headers=auth).json()
    client.post(f"/api/twin/{PID}/reset", headers=auth)
    wb = a["band_before"]["hi"] - a["band_before"]["lo"]
    wa = a["band_after"]["hi"] - a["band_after"]["lo"]
    assert a["width_change"]["now"]["before"] == pytest.approx(wb, abs=0.11)
    assert a["width_change"]["now"]["after"] == pytest.approx(wa, abs=0.11)
    assert a["width_change"]["now"]["signed_pct"] == pytest.approx((wa - wb) / wb * 100, abs=0.11)


def test_assimilate_and_reset(client, auth) -> None:
    before = client.get(f"/api/twin/{PID}/state", params={"ladder": "2"}, headers=auth).json()
    r = client.post(f"/api/twin/{PID}/assimilate", json={"ladder": "2", "value": before["estimate"], "unit": "mg/dL"},
                    headers=auth)
    assert r.status_code == 200
    a = r.json()
    assert a["band_before"] == before["band"]
    assert a["narrowed_pct"] == pytest.approx(-a["width_change"]["h120"]["signed_pct"], abs=0.051)
    assert "innovation" in a and a["safety"]["level"] == "ok" and a["safety"]["emergency"] is False
    after = client.get(f"/api/twin/{PID}/state", params={"ladder": "2"}, headers=auth).json()
    assert after["last_observation"]["kind"] == "fingerprick"
    assert after["freshness"]["label"] == "fresh"
    assert client.post(f"/api/twin/{PID}/reset", headers=auth).json() == {"ok": True}
    again = client.get(f"/api/twin/{PID}/state", params={"ladder": "2"}, headers=auth).json()
    assert again["band"] == before["band"]


def test_outlook(client, auth) -> None:
    o = client.get(f"/api/twin/{PID}/outlook_90d", params={"ladder": "2"}, headers=auth).json()
    assert o["label"] == "projection" and len(o["days"]) == len(o["tir_scenario"])


@pytest.mark.parametrize("method,path,kw", [
    ("get", f"/api/twin/{PID}/state", {"params": {"ladder": "7"}}),
    ("get", f"/api/twin/{PID}/next_best_prick", {"params": {"ladder": "x"}}),
    ("post", f"/api/twin/{PID}/forecast", {"json": {"ladder": "2", "horizon_min": 0}}),
    ("post", f"/api/twin/{PID}/forecast", {"json": {"ladder": "2", "meal": {"carbs": -5}}}),
    ("post", f"/api/twin/{PID}/forecast", {"json": {"ladder": "2", "meal": {"carbs": 10,
                                                                           "items": [{"food_id": "nope"}]}}}),
    ("post", f"/api/twin/{PID}/assimilate", {"json": {"ladder": "2", "value": 5, "unit": "mg/dL"}}),
    ("post", f"/api/twin/{PID}/assimilate", {"json": {"ladder": "2", "value": 140}}),  # unit is required
    ("post", f"/api/twin/{PID}/assimilate", {"json": {"ladder": "2", "value": 140, "unit": "mg%"}}),
    ("post", f"/api/twin/{PID}/assimilate", {"json": {"ladder": "2", "value": 40, "unit": "mmol/L"}}),
    ("post", f"/api/twin/{PID}/assimilate", {"json": {"ladder": "2"}}),
    ("post", f"/api/twin/{PID}/advance", {"json": {"ladder": "2", "minutes": 5}}),
    ("post", f"/api/twin/{PID}/advance", {"json": {"ladder": "2", "minutes": 241}}),
])
def test_bad_input_is_422(client, auth, method: str, path: str, kw: dict) -> None:
    r = getattr(client, method)(path, headers=auth, **kw)
    assert r.status_code == 422, r.text


def test_unknown_persona_is_404(client, auth) -> None:
    assert client.get("/api/twin/nobody/state", headers=auth).status_code == 404
    assert client.post("/api/twin/nobody/forecast", json={"ladder": "2"}, headers=auth).status_code == 404


def test_openapi_documents_section_46(client) -> None:
    spec = client.get("/openapi.json").json()
    for method, path in SECTION_46:
        op = spec["paths"][path][method]
        assert "twin" in op["tags"], path
        assert op.get("summary"), path
        schema = op["responses"]["200"]["content"]["application/json"]["schema"]
        assert "$ref" in schema, path  # typed response model


# ----------------------------------------------------------------------------- agent
def test_agent_chat_dose_blocked(client, auth) -> None:
    r = client.post("/api/agent/chat", json={"patient_id": PID, "text": "How much insulin should I take?",
                                             "lang": "en-IN", "ladder": "2"}, headers=auth).json()
    assert r["safety"]["blocked"] is True and r["tool_calls"] == [] and r["source"] in ("fixture", "live")


@pytest.mark.parametrize("lang,text", [("en-IN", "My father fainted"), ("bn-IN", "বাবা অজ্ঞান হয়ে গেছেন")])
def test_agent_chat_emergency(client, auth, lang: str, text: str) -> None:
    r = client.post("/api/agent/chat", json={"patient_id": PID, "text": text, "lang": lang, "ladder": "2"},
                    headers=auth).json()
    assert r["safety"]["emergency"] is True and "108" in r["reply"]


@pytest.mark.parametrize("lang,text", [
    ("hi-IN", "अगर मैं अभी चावल और दाल खाऊँ तो क्या होगा?"),
    ("kn-IN", "ನಾನು ಈಗ ರಾಗಿ ಮುದ್ದೆ ಮತ್ತು ಸಾರು ತಿಂದರೆ ಏನಾಗುತ್ತದೆ?"),
    ("en-IN", "how am i now"),
])
def test_agent_chat_grounded(client, auth, lang: str, text: str) -> None:
    r = client.post("/api/agent/chat", json={"patient_id": PID, "text": text, "lang": lang, "ladder": "2"},
                    headers=auth)
    assert r.status_code == 200
    r = r.json()
    assert r["grounding"]["passed"] and r["source"] == "fixture" and r["lang"] == lang
    assert r["highlight"]["view"] in ("stage", "forecast", "whatif", "nbp", "none")
    if "खाऊँ" in text or "ತಿಂದರೆ" in text:
        fc = next(c for c in r["tool_calls"] if c["name"] == "forecast")
        assert len(fc["args"]["items"]) == 2


def test_agent_chat_validation(client, auth) -> None:
    assert client.post("/api/agent/chat", json={"patient_id": PID, "text": "", "lang": "en-IN"},
                       headers=auth).status_code == 422
    assert client.post("/api/agent/chat", json={"patient_id": "x", "text": "hi", "lang": "en-IN"},
                       headers=auth).status_code == 404


# ----------------------------------------------------------------------------- food, lab & FHIR, reports
def test_food_search_and_swaps(client, auth) -> None:
    out = client.get("/api/food/search", params={"q": "चावल", "lang": "hi-IN"}, headers=auth).json()
    assert out[0]["id"] == "white_rice_katori"
    assert client.get("/api/food/swaps", headers=auth).json()


def test_lab_confirm_and_fhir_bundle(client, auth) -> None:
    fields = [{"code": "hba1c", "name": "HbA1c", "value": 7.4, "unit": "%", "ref_range": "4.0-5.6",
               "implausible": False, "loinc": "4548-4"},
              {"code": "medication", "name": "Medication", "value": "Metformin 500 mg", "unit": "", "ref_range": "",
               "implausible": False}]
    r = client.post("/api/lab/confirm", json={"patient_id": PID, "fields": fields}, headers=auth)
    assert r.status_code == 200 and r.json()["resource_count"] == 2  # obs + medication; no condition from a value
    bad = [{**fields[0], "value": "seven"}]
    assert client.post("/api/lab/confirm", json={"patient_id": PID, "fields": bad}, headers=auth).status_code == 422
    b = client.get(f"/api/fhir/{PID}/bundle", headers=auth)
    assert b.status_code == 200 and "attachment" in b.headers["content-disposition"]
    bundle = b.json()
    assert bundle["resourceType"] == "Bundle"
    fr = pytest.importorskip("fhir.resources.R4B.bundle")
    fr.Bundle.model_validate(bundle)
    kinds = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert kinds[0] == "Patient" and "Observation" in kinds


def test_reports(client, auth) -> None:
    lst = client.get("/api/reports", headers=auth).json()
    names = {x["name"] for x in lst}
    assert "summary" in names
    s = client.get("/api/reports/summary", headers=auth)
    assert s.status_code == 200 and isinstance(s.json(), dict)
    assert client.get("/api/reports/not_a_report", headers=auth).status_code == 404


def test_doctor_panel_and_brief(client, auth) -> None:
    panel = client.get("/api/doctor/panel", headers=auth).json()
    risks = [p["risk_7d"] for p in panel]
    assert risks == sorted(risks, reverse=True)
    brief = client.get(f"/api/doctor/brief/{PID}", headers=auth).json()
    assert len(brief["daily_profile"]["t"]) == 48 and brief["suggestions"]
    assert not any("dose" in s.lower() for s in brief["suggestions"])


# ----------------------------------------------------------------------------- every remaining route
COVERED_ROUTES = {
    "/api/health", "/api/auth/login", "/api/auth/me", "/api/patients", "/api/patients/{pid}",
    "/api/twin/{pid}/state", "/api/twin/{pid}/forecast", "/api/twin/{pid}/what_if", "/api/twin/{pid}/next_best_prick",
    "/api/twin/{pid}/assimilate", "/api/twin/{pid}/outlook_90d", "/api/twin/{pid}/explain/{forecast_id}",
    "/api/twin/{pid}/reset", "/api/food/search", "/api/food/swaps", "/api/meal/samples", "/api/meal/photo",
    "/api/samples/{kind}/{name}", "/api/agent/chat", "/api/audio/{name}", "/api/speech/stt", "/api/speech/tts",
    "/api/demo/voice_samples", "/api/lab/samples", "/api/lab/parse", "/api/lab/confirm", "/api/fhir/{pid}/bundle",
    "/api/doctor/panel", "/api/doctor/brief/{pid}", "/api/reports", "/api/reports/{name}",
    "/api/reports/figures/{name}", "/api/demo/tour",
    # v3 (covered in tests/test_api_v3.py)
    "/api/ready", "/api/twin/{pid}/advance", "/api/twin/{pid}/reveal", "/api/twin/{pid}/receipt/{forecast_id}",
    "/api/agent/confirm", "/api/doctor/queue", "/api/doctor/review/{pid}",
}


def test_every_route_has_a_test() -> None:
    from pratifalan.api.main import app

    paths = {r.path for r in app.routes if getattr(r, "path", "").startswith("/api/")}
    assert paths == COVERED_ROUTES, paths ^ COVERED_ROUTES


@pytest.mark.parametrize("lang,col", [("en-IN", "label_en"), ("hi-IN", "label_hi"), ("bn-IN", "label_bn"),
                                      ("kn-IN", "label_kn")])
def test_food_swaps_localised(client, auth, lang: str, col: str) -> None:
    from pratifalan import food

    out = client.get("/api/food/swaps", params={"lang": lang}, headers=auth).json()
    raw = food.swaps()
    assert len(out) == len(raw)
    for o, r in zip(out, raw, strict=True):
        assert set(o) == {"from", "to", "from_qty", "to_qty", "label", "label_en"}
        assert o["label"] == r[col] and o["label_en"] == r["label_en"]


def test_food_search_paneer_curry(client, auth) -> None:
    out = client.get("/api/food/search", params={"q": "paneer curry"}, headers=auth).json()
    assert "paneer" in out[0]["id"]


def test_meal_samples_and_photo_by_sample_id(client, auth) -> None:
    samples = client.get("/api/meal/samples", headers=auth).json()
    assert len(samples) == 4 and all(s["image_url"].startswith("/api/samples/meals/") for s in samples)
    for s in samples:
        r = client.post("/api/meal/photo", data={"sample_id": s["id"], "lang": "hi-IN"}, headers=auth)
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["source"] == "fixture" and m["dishes"] and m["total"]["carbs"] > 0
        for d in m["dishes"]:
            assert d["needs_pick"] or d["food_id"]
    r = client.post("/api/meal/photo", data={"sample_id": "no_such_sample"}, headers=auth)
    assert r.status_code == 404  # manifest ids only
    assert client.post("/api/meal/photo", data={"sample_id": samples[0]["id"]}).status_code == 401


def test_sample_files_are_public(client, auth) -> None:
    meal = client.get("/api/meal/samples", headers=auth).json()[0]
    r = client.get(meal["image_url"])  # no bearer: <img src> must work
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/")
    lab = client.get("/api/lab/samples", headers=auth).json()[0]
    assert client.get(lab["image_url"]).status_code == 200
    assert client.get("/api/samples/other/x.png").status_code == 404
    assert client.get("/api/samples/meals/..%2F..%2Fapi%2Fmain.py").status_code == 404
    assert client.get("/api/samples/meals/missing.jpg").status_code == 404


def test_lab_samples_and_parse_by_sample_id(client, auth) -> None:
    labs = client.get("/api/lab/samples", headers=auth).json()
    assert {x["id"] for x in labs} == {"lab_haripada", "lab_ramesh"}
    for x in labs:
        r = client.post("/api/lab/parse", data={"sample_id": x["id"]}, headers=auth)
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["source"] == "fixture"
        codes = {f["code"] for f in p["fields"]}
        assert "hba1c" in codes and all(f.get("loinc") for f in p["fields"] if f["code"] != "medication")
    pdf = client.post("/api/lab/parse", files={"file": ("r.pdf", b"%PDF-1.4", "application/pdf")}, headers=auth)
    assert pdf.status_code == 415
    assert client.post("/api/lab/parse", data={"sample_id": "nope"}, headers=auth).status_code == 404


def test_signed_audio_urls(client, auth) -> None:
    from pratifalan.api import main as M

    vs = client.get("/api/demo/voice_samples", headers=auth).json()
    assert vs and all({"lang", "prompt", "audio_url"} <= set(v) for v in vs)
    url = next(v["audio_url"] for v in vs if v["audio_url"])
    assert url.startswith("/api/audio/") and "exp=" in url and "sig=" in url
    ok = client.get(url)  # no bearer needed
    assert ok.status_code == 200 and ok.headers["content-type"] == "audio/mpeg"
    path, query = url.split("?")
    assert client.get(path).status_code == 403                                   # unsigned
    assert client.get(url[:-4] + "0000").status_code == 403                      # wrong signature
    name = path.rsplit("/", 1)[1]
    expired = M.signed_audio_url(name[:-4], now=0)                                # expired long ago
    assert client.get(expired).status_code == 403
    other = M.signed_audio_url("0" * 20)                                          # valid signature, no file
    assert client.get(other).status_code == 404
    assert client.get("/api/audio/..%2Fsecret.mp3?exp=9999999999&sig=x").status_code == 404


def test_speech_routes_in_demo_mode(client, auth) -> None:
    r = client.post("/api/speech/stt", files={"audio": ("a.webm", b"\x00\x01", "audio/webm")},
                    data={"lang": "hi-IN"}, headers=auth)
    assert r.status_code == 501
    r = client.post("/api/speech/tts", json={"text": "an unrecorded sentence 12345", "lang": "en-IN"}, headers=auth)
    assert r.status_code == 404
    vs = [v for v in client.get("/api/demo/voice_samples", headers=auth).json() if v["audio_url"]]
    r = client.post("/api/speech/tts", json={"text": vs[0]["prompt"], "lang": vs[0]["lang"]}, headers=auth)
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"  # recorded demo audio
    assert client.post("/api/speech/tts", json={"text": "x", "lang": "en-IN"}).status_code == 401


def test_agent_chat_contract_fields(client, auth) -> None:
    r = client.post("/api/agent/chat", json={"patient_id": PID, "text": "if i eat 2 roti and dal", "lang": "en-IN",
                                             "ladder": "2"}, headers=auth).json()
    assert r["source"] == "fixture" and r["source_detail"] == "template"
    assert r["highlight"]["view"] == "forecast" and r["highlight"]["from"] < r["highlight"]["to"]
    assert "/" not in r["reply"]
    assert r["audio_url"] is None or "sig=" in r["audio_url"]


def test_agent_chat_low_reading_gets_hypo_message(client, auth) -> None:
    from pratifalan.agent import safety

    client.post(f"/api/twin/{PID}/reset", headers=auth)
    r = client.post("/api/agent/chat", json={"patient_id": PID, "text": "my sugar is 64", "lang": "en-IN",
                                             "ladder": "2"}, headers=auth).json()
    assert r["reply"].startswith(safety.message("hypo", "en-IN", value=64))
    assert r["pending_action"]["kind"] == "log_reading" and r["pending_action"]["id"]
    st = client.get(f"/api/twin/{PID}/state", params={"ladder": "2"}, headers=auth).json()
    assert st["last_observation"]["value"] != 64  # chat alone never mutates
    c = client.post("/api/agent/confirm", json={"action_id": r["pending_action"]["id"], "confirm": True},
                    headers=auth).json()
    assert c["reply"].startswith(safety.message("hypo", "en-IN", value=64)) and c["safety"]["level"] == "low"
    st = client.get(f"/api/twin/{PID}/state", params={"ladder": "2"}, headers=auth).json()
    assert st["last_observation"]["value"] == 64 and st["last_observation"]["source"] == "chat"
    again = client.post("/api/agent/confirm", json={"action_id": r["pending_action"]["id"], "confirm": True},
                        headers=auth)
    assert again.status_code == 404  # an action is performed once
    client.post(f"/api/twin/{PID}/reset", headers=auth)


def test_doctor_brief_driver_and_outlook_anchor(client, auth) -> None:
    brief = client.get(f"/api/doctor/brief/{PID}", headers=auth).json()
    fc = client.post(f"/api/twin/{PID}/forecast", json={"ladder": "2"}, headers=auth).json()
    assert brief["top_driver"] == fc["drivers"][0]["label_en"]  # the no-meal forecast, no invented meal
    assert "This meal" not in brief["top_driver"]
    o = client.get(f"/api/twin/{PID}/outlook_90d", params={"ladder": "2"}, headers=auth).json()
    assert o["tir_current"][0] == pytest.approx(brief["tir_7d"], abs=1e-3)
    assert o["anchor"]["source"] == "observed last 7 days"


def test_report_figures_public_and_tour(client, auth) -> None:
    from pratifalan.config import REPORTS_DIR

    figs = sorted((REPORTS_DIR / "figures").glob("*.png"))
    if figs:
        r = client.get(f"/api/reports/figures/{figs[0].name}")
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert client.get("/api/reports/figures/nope.png").status_code == 404
    t = client.get("/api/demo/tour", headers=auth).json()
    assert t["steps"] and all({"id", "title_en", "body_en", "route"} <= set(s) for s in t["steps"])
    assert client.get("/api/demo/tour").status_code == 401
