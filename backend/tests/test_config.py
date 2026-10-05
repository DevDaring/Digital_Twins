"""config.py: empty .env values never override defaults; JWT secret is never a public default."""

from __future__ import annotations

from pratifalan.config import Settings


def test_empty_values_are_ignored(monkeypatch) -> None:
    monkeypatch.setenv("LLM_TIMEOUT_S", "")
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "")
    s = Settings(_env_file=None)
    assert s.llm_timeout_s == 25.0 and s.llm_provider_order.startswith("openrouter")


def test_empty_canonical_key_does_not_hide_legacy_name(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("Open_AI_2009_Key", "legacy-test-value")
    assert Settings(_env_file=None).openai_api_key == "legacy-test-value"


def test_unset_jwt_secret_is_random_not_public(monkeypatch) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    a = Settings(_env_file=None)
    assert a.jwt_secret_generated and len(a.jwt_secret) >= 32
    assert a.jwt_secret != "dev-only-change-me-pratifalan"
    monkeypatch.setenv("JWT_SECRET", "")
    assert Settings(_env_file=None).jwt_secret_generated


def test_explicit_jwt_secret_is_used(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "explicit-test-secret")
    s = Settings(_env_file=None)
    assert s.jwt_secret == "explicit-test-secret" and not s.jwt_secret_generated
