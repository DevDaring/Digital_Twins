"""Central configuration.

Secrets are read from ``Codes/.env`` (never committed). Both the canonical
names from ``.env.example`` and the legacy names already present in the team's
shared ``.env`` are accepted, so nobody has to rename keys.
"""

from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
FOOD_DIR = DATA_DIR / "food"
REPORTS_DIR = BACKEND_DIR / "reports"
FIXTURES_DIR = BACKEND_DIR / "fixtures"
MODELS_DIR = BACKEND_DIR / "artifacts"
CACHE_DIR = DATA_DIR / "cache"
TTS_CACHE_DIR = CACHE_DIR / "tts"  # runtime text-to-speech cache (gitignored); fixtures/audio = recorded demo audio
RUNTIME_DIR = CACHE_DIR / "runtime"  # live parse results, per user (gitignored); packaged fixtures stay read-only

log = logging.getLogger("pratifalan.config")
# Used when JWT_SECRET is unset: random per process (sessions end on restart), never a public default.
_PROCESS_JWT_SECRET = secrets.token_urlsafe(48)


def _alias(*names: str) -> AliasChoices:
    return AliasChoices(*names)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_DIR / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        # "KEY=" in .env must not override a default or hide a legacy alias that has a value
        env_ignore_empty=True,
    )

    # --- App ---
    app_mode: str = Field("demo", validation_alias=_alias("APP_MODE"))
    default_language: str = Field("en-IN", validation_alias=_alias("DEFAULT_LANGUAGE"))
    database_url: str = Field(
        "postgresql+psycopg://pratibimb:pratibimb_dev_2026@localhost:5432/pratifalan",
        validation_alias=_alias("DATABASE_URL"),
    )
    jwt_secret: str = Field("", validation_alias=_alias("JWT_SECRET"))
    jwt_secret_generated: bool = False
    jwt_ttl_hours: int = 12

    # Demo login accounts seeded at start-up. Format: "user:password,user:password".
    demo_users: str = Field(
        "TestUser:TestUser11", validation_alias=_alias("DEMO_USERS")
    )

    # --- LLM providers (canonical name first, then legacy names) ---
    openrouter_api_key: str = Field(
        "", validation_alias=_alias("OPENROUTER_API_KEY", "OPENROUTER_API_KEY_1")
    )
    openrouter_api_key_2: str = Field("", validation_alias=_alias("OPENROUTER_API_KEY_2"))
    openai_api_key: str = Field("", validation_alias=_alias("OPENAI_API_KEY", "Open_AI_2009_Key"))
    deepseek_api_key: str = Field(
        "", validation_alias=_alias("DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY_1")
    )
    kimi_api_key: str = Field("", validation_alias=_alias("KIMI_API_KEY", "KIMI_2009_API_KEY"))
    xai_api_key: str = Field("", validation_alias=_alias("XAI_API_KEY", "Grok_API_KEY"))
    nanogpt_api_key: str = Field(
        "", validation_alias=_alias("NANOGPT_API_KEY", "NanoGPT_2009_API_KEY", "NanoGPT_88_API_Key")
    )
    gemini_api_key: str = Field("", validation_alias=_alias("GEMINI_API_KEY", "GEMINI_API_KEY_1"))

    # --- Speech ---
    # Up to three Sarvam keys, used round-robin with fail-over (canonical names first, then legacy).
    sarvam_api_key: str = Field("", validation_alias=_alias("SARVAM_API_KEY", "SARVAM_88_API_KEY"))
    sarvam_api_key_2: str = Field("", validation_alias=_alias("SARVAM_API_KEY_2", "SARVAM_2009_API_KEY"))
    sarvam_api_key_3: str = Field("", validation_alias=_alias("SARVAM_API_KEY_3", "SARVAM_PHD_API_KEY"))
    sarvam_tts_speaker: str = Field("priya", validation_alias=_alias("SARVAM_TTS_SPEAKER"))
    fish_audio_api_key: str = Field(
        "", validation_alias=_alias("FISH_AUDIO_API_KEY", "Fish_Audio_88_API_KEY")
    )

    # --- Model routing (per role). Empty -> provider-specific default in providers/llm.py ---
    llm_router_model: str = Field("", validation_alias=_alias("LLM_ROUTER_MODEL"))
    llm_planner_model: str = Field("", validation_alias=_alias("LLM_PLANNER_MODEL"))
    llm_vision_model: str = Field("", validation_alias=_alias("LLM_VISION_MODEL"))
    llm_translator_model: str = Field("", validation_alias=_alias("LLM_TRANSLATOR_MODEL"))
    llm_provider_order: str = Field(
        "openrouter,openai,deepseek,kimi,xai,nanogpt", validation_alias=_alias("LLM_PROVIDER_ORDER")
    )
    llm_timeout_s: float = Field(25.0, validation_alias=_alias("LLM_TIMEOUT_S"))

    # --- Ops: per-user rate limits (requests per minute) on endpoints that can cost money in live
    # mode, and hard upload size bounds (bytes are counted while the body is read).
    rate_chat_per_min: int = Field(30, validation_alias=_alias("RATE_CHAT_PER_MIN"))
    rate_stt_per_min: int = Field(12, validation_alias=_alias("RATE_STT_PER_MIN"))
    rate_tts_per_min: int = Field(30, validation_alias=_alias("RATE_TTS_PER_MIN"))
    rate_meal_photo_per_min: int = Field(8, validation_alias=_alias("RATE_MEAL_PHOTO_PER_MIN"))
    rate_lab_parse_per_min: int = Field(8, validation_alias=_alias("RATE_LAB_PARSE_PER_MIN"))
    max_image_bytes: int = Field(12 * 1024 * 1024, validation_alias=_alias("MAX_IMAGE_BYTES"))
    max_audio_bytes: int = Field(10 * 1024 * 1024, validation_alias=_alias("MAX_AUDIO_BYTES"))

    @model_validator(mode="after")
    def _random_jwt_secret(self) -> Settings:
        if not self.jwt_secret.strip():
            self.jwt_secret = _PROCESS_JWT_SECRET
            self.jwt_secret_generated = True
        return self

    @property
    def sarvam_keys(self) -> list[str]:
        return [k for k in (self.sarvam_api_key, self.sarvam_api_key_2, self.sarvam_api_key_3) if k.strip()]

    @property
    def live(self) -> bool:
        return self.app_mode.strip().lower() == "live"

    def demo_user_pairs(self) -> list[tuple[str, str]]:
        out = []
        for item in self.demo_users.split(","):
            if ":" in item:
                u, p = item.split(":", 1)
                out.append((u.strip(), p.strip()))
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()
