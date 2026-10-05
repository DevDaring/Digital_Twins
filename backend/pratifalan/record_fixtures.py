"""Record the offline-demo fixtures and measure the live voice round trip (needs APP_MODE=live).

Steps (run all by default, or pick with ``--steps``):

``vision``     Live vision parse of every sample meal photo and lab report through
               ``perception.meal.parse`` / ``perception.lab.parse`` (with ``sample_id``), which
               writes ``fixtures/meal_parse/<id>.json`` and ``fixtures/lab_parse/<id>.json``.
               Lab values are scored against the synthetic reports' ground truth.
``voice``      ``fixtures/voice_samples.json``: 3 prompts per language (forecast with a local
               dish, what-if, next check).
``audio``      TTS for every voice-sample PROMPT and for the DEMO-MODE (template) agent REPLY to
               it for each persona (ladder 2, no events), saved as
               ``fixtures/audio/<sha1(f"{lang}|{text}")[:20]>.mp3`` - the key the API looks up.
``roundtrip``  Live voice round trip per voice sample: TTS(prompt) -> STT -> character error rate ->
               live agent on the transcript -> TTS(reply), with per-stage latency and
               time-to-first-audio -> ``reports/voice_roundtrip.json``.

    APP_MODE=live LLM_VISION_MODEL=... LLM_ROUTER_MODEL=... LLM_PLANNER_MODEL=... \\
        .venv/bin/python -m pratifalan.record_fixtures [--steps vision,voice,audio,roundtrip] [--force]

Audio and secrets are never logged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
import unicodedata
from datetime import UTC, datetime
from typing import Any

from pratifalan.config import FIXTURES_DIR, REPORTS_DIR, get_settings

AUDIO_DIR = FIXTURES_DIR / "audio"
VOICE_SAMPLES = FIXTURES_DIR / "voice_samples.json"
ROUNDTRIP_REPORT = REPORTS_DIR / "voice_roundtrip.json"
PERSONAS = ("haripada", "lakshmi", "ramesh")
LADDER = "2"
TTFA_TARGET_S = 2.5
# Persona whose home language this is (used for the live round trip).
LANG_PERSONA = {"en-IN": "haripada", "hi-IN": "ramesh", "bn-IN": "haripada", "kn-IN": "lakshmi"}

# Prompts chosen to showcase the three core moves with local dishes; each is also in the
# agent suite, where the template path answers it with the intended tool.
VOICE_SAMPLES_DATA = [
    {"lang": "en-IN", "kind": "forecast", "prompt": "If I have 2 rotis with a katori of dal for dinner now, how high will my sugar go?"},
    {"lang": "en-IN", "kind": "what_if", "prompt": "What if I eat only half the rice with my fish curry tonight?"},
    {"lang": "en-IN", "kind": "next_check", "prompt": "When should I check my sugar next?"},
    {"lang": "hi-IN", "kind": "forecast", "prompt": "अगर मैं अभी 2 रोटी और एक कटोरी अरहर दाल खाऊँ तो मेरी शुगर कितनी बढ़ेगी?"},
    {"lang": "hi-IN", "kind": "what_if", "prompt": "अगर राजमा चावल खाने के बाद 20 मिनट टहलूँ तो कितना फ़र्क पड़ेगा?"},
    {"lang": "hi-IN", "kind": "next_check", "prompt": "अगली बार शुगर कब जाँच करूँ?"},
    {"lang": "bn-IN", "kind": "forecast", "prompt": "রাতে ভাত আর মাছের ঝোল খেলে সুগার কত উঠবে?"},
    {"lang": "bn-IN", "kind": "what_if", "prompt": "আজ রাতে ভাত অর্ধেক করে খেলে কী হবে? সঙ্গে ডাল আর মাছের ঝোল।"},
    {"lang": "bn-IN", "kind": "next_check", "prompt": "পরের বার সুগার কখন মাপব?"},
    {"lang": "kn-IN", "kind": "forecast", "prompt": "ಈಗ ಎರಡು ರಾಗಿ ಮುದ್ದೆ ಮತ್ತು ಸಾರು ತಿಂದರೆ ನನ್ನ ಸಕ್ಕರೆ ಎಷ್ಟು ಏರುತ್ತದೆ?"},
    {"lang": "kn-IN", "kind": "what_if", "prompt": "ಚಿತ್ರಾನ್ನ ತಿಂದ ಮೇಲೆ 20 ನಿಮಿಷ ನಡೆದರೆ ಎಷ್ಟು ಸಹಾಯ ಆಗುತ್ತದೆ?"},
    {"lang": "kn-IN", "kind": "next_check", "prompt": "ಮುಂದಿನ ಸಲ ಸಕ್ಕರೆ ಯಾವಾಗ ಪರೀಕ್ಷಿಸಬೇಕು?"},
]


# ----------------------------------------------------------------------------- helpers
def audio_key(text: str, lang: str) -> str:
    """Same key as the API (``api.main._audio_key``)."""
    return hashlib.sha1(f"{lang}|{text}".encode()).hexdigest()[:20]


def set_mode(mode: str) -> None:
    os.environ["APP_MODE"] = "live" if mode == "live" else "demo"
    get_settings.cache_clear()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _log(msg: str) -> None:
    print(msg, flush=True)


def normalise_for_cer(text: str) -> str:
    from pratifalan.agent.verifier import normalise_digits

    t = unicodedata.normalize("NFC", normalise_digits(text.lower()))
    t = "".join(" " if unicodedata.category(ch).startswith(("P", "S")) else ch for ch in t)
    t = t.replace("‌", "").replace("‍", "")
    return " ".join(t.split())


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(ref: str, hyp: str) -> float:
    r, h = normalise_for_cer(ref), normalise_for_cer(hyp)
    return levenshtein(r, h) / max(len(r), 1)


# ----------------------------------------------------------------------------- step: vision
def step_vision() -> dict:
    from pratifalan.perception import lab, meal
    from pratifalan.providers.llm import LLMUnavailable, available

    set_mode("live")
    if not available("vision"):
        raise SystemExit("vision step needs APP_MODE=live and LLM_VISION_MODEL with a provider key")
    out: dict[str, Any] = {"meals": [], "labs": []}
    for s in meal.samples():
        t0 = time.perf_counter()
        try:
            r = meal.record_fixture(s["id"])  # the only writer of packaged meal fixtures
            ok = r.get("source") == "live"
            rec = {"id": s["id"], "ok": ok, "source": r.get("source"), "model": r.get("model"),
                   "dishes": [{"detected": d["detected"], "food_id": d["food_id"], "units": d["units"],
                               "needs_pick": d["needs_pick"]} for d in r["dishes"]],
                   "total_carbs": r["total"]["carbs"], "carbs_sd": r["carbs_sd"]}
        except (LLMUnavailable, ValueError) as exc:
            rec = {"id": s["id"], "ok": False, "error": str(exc)[:200]}
        rec["ms"] = round((time.perf_counter() - t0) * 1000)
        out["meals"].append(rec)
        _log(f"meal {s['id']}: {'live' if rec['ok'] else 'FAILED'} "
             f"{len(rec.get('dishes', []))} dishes, {rec.get('total_carbs')} g carbs, {rec['ms']} ms")
    truth = {t["id"]: t.get("ground_truth", {}) for t in json.loads((lab.SAMPLES_DIR / "samples.json").read_text())}
    key_map = {"fasting_glucose": "fpg"}
    for s in lab.samples():
        t0 = time.perf_counter()
        try:
            r = lab.record_fixture(s["id"])  # the only writer of packaged lab fixtures
            gt = truth.get(s["id"], {})
            fields = {f["code"]: f["value"] for f in r["fields"] if f["code"] != "medication"}
            meds = [f["value"] for f in r["fields"] if f["code"] == "medication"]
            scored = {}
            for code in lab.FIELDS:
                want = gt.get(key_map.get(code, code))
                if want is None:
                    continue
                got = fields.get(code)
                scored[code] = {"truth": want, "parsed": got,
                                "match": got is not None and abs(float(got) - float(want)) <= 1e-6}
            n_ok = sum(v["match"] for v in scored.values())
            rec = {"id": s["id"], "ok": r.get("source") == "live", "source": r.get("source"), "model": r.get("model"),
                   "fields_correct": n_ok, "fields_total": len(scored), "fields": scored, "medications": meds,
                   "medications_truth": gt.get("medications", [])}
        except (LLMUnavailable, ValueError) as exc:
            rec = {"id": s["id"], "ok": False, "error": str(exc)[:200]}
        rec["ms"] = round((time.perf_counter() - t0) * 1000)
        out["labs"].append(rec)
        _log(f"lab {s['id']}: {'live' if rec['ok'] else 'FAILED'} "
             f"{rec.get('fields_correct')}/{rec.get('fields_total')} fields exact, {rec['ms']} ms")
    return out


# ----------------------------------------------------------------------------- step: voice samples
def step_voice() -> list[dict]:
    VOICE_SAMPLES.parent.mkdir(parents=True, exist_ok=True)
    VOICE_SAMPLES.write_text(json.dumps(VOICE_SAMPLES_DATA, ensure_ascii=False, indent=1), encoding="utf-8")
    _log(f"wrote {VOICE_SAMPLES} ({len(VOICE_SAMPLES_DATA)} prompts)")
    return VOICE_SAMPLES_DATA


# ----------------------------------------------------------------------------- step: audio
def demo_replies() -> list[dict]:
    """Template-mode replies the offline demo will show for each voice sample x persona."""
    set_mode("demo")
    from pratifalan.agent.orchestrator import Agent
    from pratifalan.twin.engine import get_engine

    agent = Agent(get_engine())
    out = []
    for s in json.loads(VOICE_SAMPLES.read_text()):
        for pid in PERSONAS:
            r = agent.handle(s["prompt"], s["lang"], pid, LADDER, [])
            out.append({"lang": s["lang"], "persona": pid, "prompt": s["prompt"], "reply": r["reply"],
                        "intent": r["intent"], "grounded": r["grounding"]["passed"],
                        "tools": [c["name"] for c in r["tool_calls"]]})
    return out


def _tts_to_file(text: str, lang: str, force: bool) -> dict:
    from pratifalan.providers import speech

    key = audio_key(text, lang)
    p = AUDIO_DIR / f"{key}.mp3"
    if p.exists() and not force:
        return {"key": key, "status": "exists", "bytes": p.stat().st_size}
    t0 = time.perf_counter()
    audio, mime, prov = speech.tts(text, lang)
    ms = round((time.perf_counter() - t0) * 1000)
    if mime != "audio/mpeg":
        return {"key": key, "status": f"skipped: provider {prov} returned {mime}, API serves mp3 only"}
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    p.write_bytes(audio)
    return {"key": key, "status": "written", "provider": prov, "bytes": len(audio), "ms": ms}


def step_audio(force: bool) -> dict:
    from pratifalan.providers import speech

    if not VOICE_SAMPLES.exists():
        step_voice()
    replies = demo_replies()
    set_mode("live")
    jobs: list[dict] = []
    for s in json.loads(VOICE_SAMPLES.read_text()):
        jobs.append({"kind": "prompt", "lang": s["lang"], "text": s["prompt"]})
    for r in replies:
        jobs.append({"kind": "reply", "lang": r["lang"], "text": r["reply"], "persona": r["persona"],
                     "prompt": r["prompt"], "intent": r["intent"], "grounded": r["grounded"]})
    manifest, seen = [], set()
    for j in jobs:
        k = audio_key(j["text"], j["lang"])
        if k in seen:
            manifest.append({**j, "key": k, "status": "duplicate"})
            continue
        seen.add(k)
        try:
            res = _tts_to_file(j["text"], j["lang"], force)
        except speech.SpeechUnavailable as exc:
            res = {"key": k, "status": f"failed: {str(exc)[:160]}"}
        manifest.append({**j, **res})
        _log(f"audio {j['kind']:<6} {j['lang']} {j.get('persona', ''):<9} {res['status']} {res.get('ms', '')}")
    (AUDIO_DIR / "manifest.json").write_text(json.dumps({"generated_at": _now(), "files": manifest},
                                                        ensure_ascii=False, indent=1), encoding="utf-8")
    counts: dict[str, int] = {}
    for m in manifest:
        st = m["status"].split(":")[0]
        counts[st] = counts.get(st, 0) + 1
    return {"jobs": len(jobs), "unique": len(seen), "status_counts": counts,
            "replies_grounded": sum(r["grounded"] for r in replies), "replies": len(replies)}


# ----------------------------------------------------------------------------- step: round trip
def _tts_stream_ttfb(text: str, lang: str) -> dict:
    """Time to the first audio byte if the reply were STREAMED from OpenAI TTS (a probe of what
    streaming would give; the app today synthesises the full file before playing it)."""
    import httpx

    from pratifalan.providers import speech

    key = get_settings().openai_api_key
    if not key:
        return {"skipped": "no OpenAI key"}
    body = {"model": speech.OPENAI_TTS_MODEL, "voice": speech.OPENAI_TTS_VOICE, "input": text,
            "response_format": "mp3"}
    t0 = time.perf_counter()
    first = None
    n = 0
    try:
        with httpx.stream("POST", "https://api.openai.com/v1/audio/speech", json=body,
                          headers={"Authorization": f"Bearer {key}"}, timeout=40) as r:
            r.raise_for_status()
            for chunk in r.iter_bytes():
                if chunk and first is None:
                    first = time.perf_counter() - t0
                n += len(chunk)
    except Exception as exc:  # noqa: BLE001
        return {"error": type(exc).__name__}
    return {"ttfb_ms": round((first or 0) * 1000), "total_ms": round((time.perf_counter() - t0) * 1000), "bytes": n}


def med(xs: list, nd: int = 1) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), nd) if xs else None

def agg(rs: list[dict]) -> dict:
    """Round-trip summary over a list of trips."""
    ok = [r for r in rs if "error" not in r]
    return {
        "n": len(rs), "errors": len(rs) - len(ok),
        "median_cer": med([r["cer"] for r in ok], 4),
        "mean_cer": round(statistics.mean([r["cer"] for r in ok]), 4) if ok else None,
        "intent_preserved_rate": round(sum(r["intent_on_prompt_rules"] == r["intent_on_transcript_rules"]
                                           for r in ok) / len(ok), 4) if ok else None,
        "median_stt_ms": med([r["stt_ms"] for r in ok]),
        "median_agent_ms": med([r["agent_ms"] for r in ok]),
        "median_tts_reply_ms": med([r["tts_reply_ms"] for r in ok]),
        "median_ttfa_ms": med([r["ttfa_ms"] for r in ok]),
        "max_ttfa_ms": max([r["ttfa_ms"] for r in ok], default=None),
        "median_ttfa_if_streamed_ms": med([r.get("ttfa_if_streamed_ms") for r in ok]),
        "share_meeting_2_5s": round(sum(r["meets_target"] for r in ok) / len(ok), 4) if ok else None,
        "grounding_pass_rate": round(sum(r["grounding_passed"] for r in ok) / len(ok), 4) if ok else None,
        "fallback_rate": round(sum(bool(r["fallback_used"]) for r in ok) / len(ok), 4) if ok else None,
    }


def step_roundtrip(label: str) -> dict:
    from pratifalan.agent.orchestrator import Agent, rule_intent
    from pratifalan.providers import speech
    from pratifalan.providers.llm import _role_chain, available
    from pratifalan.twin.engine import get_engine

    set_mode("live")
    if not available("planner"):
        raise SystemExit("roundtrip needs APP_MODE=live and LLM_PLANNER_MODEL")
    agent = Agent(get_engine())
    for pid in set(LANG_PERSONA.values()):
        get_engine().state(pid, LADDER, [])  # warm caches like a running server
    trips = []
    for s in json.loads(VOICE_SAMPLES.read_text()):
        lang, prompt = s["lang"], s["prompt"]
        pid = LANG_PERSONA[lang]
        rec: dict[str, Any] = {"lang": lang, "kind": s.get("kind"), "persona": pid, "prompt": prompt}
        try:
            t0 = time.perf_counter()
            audio, mime, prov = speech.tts(prompt, lang)
            rec["tts_prompt_ms"] = round((time.perf_counter() - t0) * 1000)
            rec["tts_provider"] = prov
            t0 = time.perf_counter()
            transcript, stt_prov = speech.stt(audio, lang, "prompt.mp3", mime)
            rec["stt_ms"] = round((time.perf_counter() - t0) * 1000)
            rec["stt_provider"] = stt_prov
            rec["transcript"] = transcript
            rec["cer"] = round(cer(prompt, transcript), 4)
            rec["intent_on_prompt_rules"] = rule_intent(prompt)[0]
            rec["intent_on_transcript_rules"] = rule_intent(transcript)[0]
            t0 = time.perf_counter()
            out = agent.handle(transcript, lang, pid, LADDER, [])
            rec["agent_ms"] = round((time.perf_counter() - t0) * 1000)
            rec.update({"reply": out["reply"], "intent": out["intent"], "source_detail": out.get("source_detail"),
                        "grounding_passed": out["grounding"]["passed"],
                        "fallback_used": out["grounding"].get("fallback_used"),
                        "tools": [c["name"] for c in out["tool_calls"]]})
            t0 = time.perf_counter()
            reply_audio, _m, _p = speech.tts(out["reply"], lang)
            rec["tts_reply_ms"] = round((time.perf_counter() - t0) * 1000)
            rec["reply_audio_bytes"] = len(reply_audio)
            rec["ttfa_ms"] = rec["stt_ms"] + rec["agent_ms"] + rec["tts_reply_ms"]
            probe = _tts_stream_ttfb(out["reply"], lang)
            rec["tts_reply_stream_probe"] = probe
            if "ttfb_ms" in probe:
                rec["ttfa_if_streamed_ms"] = rec["stt_ms"] + rec["agent_ms"] + probe["ttfb_ms"]
            rec["meets_target"] = rec["ttfa_ms"] <= TTFA_TARGET_S * 1000
        except (speech.SpeechUnavailable, Exception) as exc:  # noqa: BLE001 - recorded, not hidden
            rec["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        trips.append(rec)
        _log(f"trip {lang} {s.get('kind'):<10} cer={rec.get('cer')} stt={rec.get('stt_ms')} agent={rec.get('agent_ms')} "
             f"tts={rec.get('tts_reply_ms')} ttfa={rec.get('ttfa_ms')} ms {rec.get('error', '')}")

    langs = sorted({t["lang"] for t in trips})
    return {"label": label, "run_at": _now(),
            "models": {role: [f"{p}:{m}" for p, m in _role_chain(role)] for role in ("router", "planner")},
            "summary": agg(trips), "by_language": {lg: agg([t for t in trips if t["lang"] == lg]) for lg in langs},
            "trips": trips}


def write_roundtrip(run: dict) -> None:
    rep: dict[str, Any] = {}
    if ROUNDTRIP_REPORT.exists():
        try:
            rep = json.loads(ROUNDTRIP_REPORT.read_text())
        except json.JSONDecodeError:
            rep = {}
    runs = rep.get("runs", {})
    runs[run["label"]] = run
    primary = runs.get("live") or run
    rep = {
        "generated_at": _now(),
        "generated_by": "python -m pratifalan.record_fixtures --steps roundtrip",
        "target_ttfa_s": TTFA_TARGET_S,
        "headline": {"n_trips": primary["summary"]["n"], "median_cer": primary["summary"]["median_cer"],
                     "median_ttfa_ms": primary["summary"]["median_ttfa_ms"],
                     "share_meeting_2_5s": primary["summary"]["share_meeting_2_5s"],
                     "median_stt_ms": primary["summary"]["median_stt_ms"],
                     "median_agent_ms": primary["summary"]["median_agent_ms"],
                     "median_tts_reply_ms": primary["summary"]["median_tts_reply_ms"]},
        "method": ("Per voice sample: TTS(prompt) stands in for the user's voice; STT transcribes it; character "
                   "error rate (CER) = Levenshtein(prompt, transcript) / len(prompt) after lower-casing, digit "
                   "normalisation and punctuation removal; the live agent answers the transcript; TTS speaks the "
                   "reply. Time-to-first-audio (TTFA) = STT + agent + full reply synthesis, i.e. what the app does "
                   "today (non-streaming; browser playback and network to the client not included). "
                   "'ttfa_if_streamed' replaces full synthesis by the first byte of a streamed OpenAI TTS response "
                   "(a probe, not implemented in the app)."),
        "caveat": ("Synthetic speech in, not real speakers: CER here is a lower bound for real users. "
                   "Latencies were measured from one server under heavy CPU load from other jobs."),
        "runs": runs,
    }
    ROUNDTRIP_REPORT.parent.mkdir(parents=True, exist_ok=True)
    ROUNDTRIP_REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    _log(f"wrote {ROUNDTRIP_REPORT}")


# ----------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", default="vision,voice,audio,roundtrip")
    ap.add_argument("--force", action="store_true", help="re-synthesise audio files that already exist")
    ap.add_argument("--label", default="live", help="name of this round-trip run in the report")
    ap.add_argument("--resummarise", action="store_true", help="re-aggregate stored round trips (no API calls)")
    a = ap.parse_args(argv)
    if not get_settings().live:
        _log("APP_MODE is not 'live'; live steps will switch it on for their calls.")
    steps = [s.strip() for s in a.steps.split(",") if s.strip()]
    if a.resummarise:
        rep = json.loads(ROUNDTRIP_REPORT.read_text())
        for run in rep["runs"].values():
            run["summary"] = agg(run["trips"])
            run["by_language"] = {lg: agg([t for t in run["trips"] if t["lang"] == lg])
                                  for lg in sorted({t["lang"] for t in run["trips"]})}
        for run in rep["runs"].values():
            write_roundtrip(run)
        return 0
    summary: dict[str, Any] = {}
    if "vision" in steps:
        summary["vision"] = step_vision()
    if "voice" in steps:
        step_voice()
    if "audio" in steps:
        summary["audio"] = step_audio(a.force)
    if "roundtrip" in steps:
        run = step_roundtrip(a.label)
        write_roundtrip(run)
        summary["roundtrip"] = run["summary"]
    if "vision" in summary:
        v = summary["vision"]
        summary["vision"] = {"meals_live": sum(m["ok"] for m in v["meals"]), "meals": len(v["meals"]),
                             "labs_live": sum(m["ok"] for m in v["labs"]), "labs": len(v["labs"]),
                             "lab_fields_correct": sum(m.get("fields_correct", 0) for m in v["labs"]),
                             "lab_fields_total": sum(m.get("fields_total", 0) for m in v["labs"]),
                             "detail": v}
    print(json.dumps(summary, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
