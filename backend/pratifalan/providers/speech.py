"""Speech-to-text and text-to-speech adapters (spec section 6.2).

Order of preference (first one with a key wins, the rest are fall-backs):

* STT: Sarvam AI (saarika) -> OpenAI (gpt-4o-mini-transcribe) -> browser Web Speech API
* TTS: Sarvam AI (bulbul) -> OpenAI (gpt-4o-mini-tts) -> Fish Audio -> browser speechSynthesis

The team's .env has no Sarvam key, so OpenAI is the live path today; the Sarvam
adapter follows Sarvam's published REST API and switches on as soon as
SARVAM_API_KEY is set (see docs/DEVIATIONS.md). Audio is never logged.
"""

from __future__ import annotations

import base64
import logging

import httpx

from pratifalan.config import get_settings

log = logging.getLogger("pratifalan.speech")

ISO = {"en-IN": "en", "hi-IN": "hi", "bn-IN": "bn", "kn-IN": "kn"}
OPENAI_TTS_VOICE = "coral"
OPENAI_STT_MODEL = "gpt-4o-mini-transcribe"
OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
SARVAM_STT_MODEL = "saarika:v2.5"
SARVAM_TTS_MODEL = "bulbul:v2"
LANG_NAME = {"en-IN": "Indian English", "hi-IN": "Hindi", "bn-IN": "Bengali", "kn-IN": "Kannada"}


class SpeechUnavailable(RuntimeError):
    pass


def stt(audio: bytes, lang: str, filename: str = "speech.webm", mime: str = "audio/webm") -> tuple[str, str]:
    s = get_settings()
    if not s.live:
        raise SpeechUnavailable("demo mode")
    errors = []
    if s.sarvam_api_key:
        try:
            r = httpx.post(
                "https://api.sarvam.ai/speech-to-text",
                headers={"api-subscription-key": s.sarvam_api_key},
                files={"file": (filename, audio, mime)},
                data={"model": SARVAM_STT_MODEL, "language_code": lang},
                timeout=30,
            )
            r.raise_for_status()
            return r.json().get("transcript", ""), "sarvam"
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
    if s.sarvam_api_key:
        try:
            r = httpx.post(
                "https://api.sarvam.ai/text-to-speech",
                headers={"api-subscription-key": s.sarvam_api_key},
                json={"text": text, "target_language_code": lang, "model": SARVAM_TTS_MODEL},
                timeout=30,
            )
            r.raise_for_status()
            audio = base64.b64decode(r.json()["audios"][0])
            return audio, "audio/wav", "sarvam"
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
