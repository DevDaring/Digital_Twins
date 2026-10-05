"""providers/llm.py: request bodies for reasoning models and fall-through on bad answers (no network)."""

from __future__ import annotations

import json

import pytest

from pratifalan.providers import llm as L


def test_openrouter_body_asks_for_low_hidden_reasoning() -> None:
    b = L.build_body("openrouter", "openai/gpt-5.4-mini", [], None, True, 0.2, 300)
    assert b["reasoning"] == {"effort": "low", "exclude": True}
    assert b["max_tokens"] == 300 and b["response_format"] == {"type": "json_object"}


def test_openrouter_anthropic_has_no_reasoning_block() -> None:
    assert "reasoning" not in L.build_body("openrouter", "anthropic/claude-sonnet-5.5", [], None, False, 0.2, 800)


@pytest.mark.parametrize("model", ["gpt-5.4-mini", "gpt-5", "o4-mini", "o3"])
def test_direct_openai_reasoning_models_use_max_completion_tokens(model: str) -> None:
    b = L.build_body("openai", model, [], None, False, 0.2, 800)
    assert b["max_completion_tokens"] == 800 and "max_tokens" not in b and "temperature" not in b


def test_direct_openai_classic_model_keeps_max_tokens() -> None:
    b = L.build_body("openai", "gpt-4o-mini", [], None, False, 0.2, 800)
    assert b["max_tokens"] == 800 and "max_completion_tokens" not in b


def _resp(content: str | None, finish: str = "stop", tool_calls: list | None = None) -> dict:
    return {"choices": [{"finish_reason": finish, "message": {"content": content, "tool_calls": tool_calls}}]}


def test_parse_response_rejects_length_and_empty() -> None:
    with pytest.raises(RuntimeError, match="length"):
        L.parse_response(_resp("Your peak may", "length"), "p", "m", 1)
    with pytest.raises(RuntimeError, match="empty"):
        L.parse_response(_resp(""), "p", "m", 1)
    ok = L.parse_response(_resp(None, "tool_calls", [{"id": "1", "function": {"name": "get_state",
                                                                              "arguments": "{}"}}]), "p", "m", 1)
    assert ok.tool_calls[0]["name"] == "get_state"


class _R:
    def __init__(self, data: dict, status: int = 200) -> None:
        self._d, self.status_code, self.text = data, status, json.dumps(data)

    def json(self) -> dict:
        return self._d


@pytest.fixture()
def live_chain(monkeypatch):
    monkeypatch.setenv("APP_MODE", "live")
    monkeypatch.setenv("LLM_ROUTER_MODEL", "openrouter:a/one,openrouter:b/two,openai:gpt-5.4-mini")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    L.get_settings.cache_clear()
    yield
    L.get_settings.cache_clear()


def test_falls_through_on_truncation_and_bad_json(monkeypatch, live_chain, caplog) -> None:
    sent: list[dict] = []
    answers = [_resp('{"intent": "sta', "length"), _resp("not json at all"), _resp('{"intent": "state"}')]

    def post(url, json=None, headers=None, timeout=None):  # noqa: A002 - httpx signature
        sent.append(json)
        return _R(answers[len(sent) - 1])

    monkeypatch.setattr(L.httpx, "post", post)
    data, res = L.LLMClient().json("router", [{"role": "user", "content": "hi"}], max_tokens=40)
    assert data == {"intent": "state"} and res.provider == "openai"
    assert [b["model"] for b in sent] == ["a/one", "b/two", "gpt-5.4-mini"]
    assert sent[0]["max_tokens"] == 300  # router floor despite max_tokens=40
    assert sent[2]["max_completion_tokens"] == 300
    assert "not json at all" not in caplog.text  # failures are logged without content


def test_all_providers_failing_raises(monkeypatch, live_chain) -> None:
    monkeypatch.setattr(L.httpx, "post", lambda *a, **k: _R(_resp("")))
    with pytest.raises(L.LLMUnavailable):
        L.LLMClient().chat("router", [{"role": "user", "content": "hi"}])
