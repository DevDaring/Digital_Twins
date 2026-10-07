"""Speech-to-text and text-to-speech adapters (spec section 6.2).

Order of preference (first one with a key wins, the rest are fall-backs):

* STT: Sarvam AI (saaras:v4) -> OpenAI (gpt-4o-mini-transcribe) -> browser Web Speech API
* TTS: Sarvam AI (bulbul:v3, Indian voices) -> OpenAI (gpt-4o-mini-tts) -> Fish Audio -> browser

Sarvam is built for Indian languages, so it is the first choice for Bengali, Hindi,
Kannada and Indian English. Up to three Sarvam keys are used round-robin; a key that
fails (auth, quota, server error, timeout) is skipped for the next one before falling
back to OpenAI. Request format follows docs.sarvam.ai (checked 7 Oct 2026). Audio and
keys are never logged.
"""

from __future__ import annotations

import base64
import itertools
import logging
from collections.abc import Callable
from typing import Any

import httpx

from pratifalan.config import get_settings

log = logging.getLogger("pratifalan.speech")

ISO = {"en-IN": "en", "hi-IN": "hi", "bn-IN": "bn", "kn-IN": "kn"}
OPENAI_TTS_VOICE = "coral"
OPENAI_STT_MODEL = "gpt-4o-mini-transcribe"
OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
SARVAM_STT_MODEL = "saaras:v4"
SARVAM_TTS_MODEL = "bulbul:v3"
SARVAM_TTS_PACE = 0.95  # a touch slower than default: calm, easy to follow
_sarvam_next = itertools.count()
LANG_NAME = {"en-IN": "Indian English", "hi-IN": "Hindi", "bn-IN": "Bengali", "kn-IN": "Kannada"}


class SpeechUnavailable(RuntimeError):
    pass


def _sarvam(call: Callable[[str], httpx.Response]) -> dict[str, Any]:
    """Run ``call(key)`` with the Sarvam keys round-robin; skip a key on auth/quota/server
    errors or timeouts. Raises the last error when every key fails."""
    keys = get_settings().sarvam_keys
    start = next(_sarvam_next)
    last: Exception | None = None
    for k in range(len(keys)):
        key = keys[(start + k) % len(keys)]
        try:
            r = call(key)
            if r.status_code in (401, 403, 429) or r.status_code >= 500:
                last = RuntimeError(f"Sarvam HTTP {r.status_code} (key {(start + k) % len(keys) + 1})")
                continue
            r.raise_for_status()
            data: dict[str, Any] = r.json()
            return data
        except httpx.TimeoutException as exc:
            last = exc
    raise last or RuntimeError("no Sarvam key")


def stt(audio: bytes, lang: str, filename: str = "speech.webm", mime: str = "audio/webm") -> tuple[str, str]:
    s = get_settings()
    if not s.live:
        raise SpeechUnavailable("demo mode")
    errors = []
    if s.sarvam_keys:
        try:
            data = _sarvam(lambda key: httpx.post(
                "https://api.sarvam.ai/speech-to-text",
                headers={"api-subscription-key": key},
                files={"file": (filename, audio, mime)},
                data={"model": SARVAM_STT_MODEL, "language_code": lang, "mode": "transcribe"},
                timeout=30,
            ))
            return str(data.get("transcript", "")), "sarvam"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"sarvam: {exc}")
    if s.openai_api_key:
        try:
            r = httpx.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {s.openai_api_key}"},
                files={"file": (filename, audio, mime)},
                data={"model": OPENAI_STT_MODEL, "language": ISO.get(lang, "en")},
                timeout=30,
            )
            r.raise_for_status()
            return r.json().get("text", ""), "openai"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"openai: {exc}")
    raise SpeechUnavailable("; ".join(errors) or "no STT provider key")


def tts(text: str, lang: str) -> tuple[bytes, str, str]:
    """Return (audio bytes, mime type, provider)."""
    s = get_settings()
    if not s.live:
        raise SpeechUnavailable("demo mode")
    errors = []
    if s.sarvam_keys:
        try:
            data = _sarvam(lambda key: httpx.post(
                "https://api.sarvam.ai/text-to-speech",
                headers={"api-subscription-key": key},
                json={"text": text[:2400], "language_code": lang, "model": SARVAM_TTS_MODEL,
                      "speaker": s.sarvam_tts_speaker, "pace": SARVAM_TTS_PACE, "output_audio_codec": "mp3",
                      "speech_sample_rate": 24000},
                timeout=30,
            ))
            return base64.b64decode(data["audios"][0]), "audio/mpeg", "sarvam"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"sarvam: {exc}")
    if s.openai_api_key:
        try:
            r = httpx.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {s.openai_api_key}"},
                json={
                    "model": OPENAI_TTS_MODEL, "voice": OPENAI_TTS_VOICE, "input": text, "response_format": "mp3",
                    "instructions": (f"Speak in natural {LANG_NAME.get(lang, 'English')} with a warm, calm, "
                                     "unhurried tone, like a kind family doctor. Pronounce numbers naturally."),
                },
                timeout=40,
            )
            r.raise_for_status()
            return r.content, "audio/mpeg", "openai"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"openai: {exc}")
    if s.fish_audio_api_key:
        try:
            r = httpx.post(
                "https://api.fish.audio/v1/tts",
                headers={"Authorization": f"Bearer {s.fish_audio_api_key}", "model": "s1"},
                json={"text": text, "format": "mp3"},
                timeout=40,
            )
            r.raise_for_status()
            return r.content, "audio/mpeg", "fish"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"fish: {exc}")
    raise SpeechUnavailable("; ".join(errors) or "no TTS provider key")
