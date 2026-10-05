"""One ``LLMClient`` for every role (router, planner, vision, translator).

All six supported providers expose an OpenAI-compatible Chat Completions API, so one
thin adapter per provider (base URL + key) is enough. Model IDs are never hard-coded:
each role reads ``LLM_<ROLE>_MODEL`` from ``.env`` as a comma-separated list of
``provider:model`` pairs, tried in order (then ``LLM_PROVIDER_ORDER`` decides which
providers are eligible at all). On timeout or error the next pair is tried.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from pratifalan.config import get_settings

log = logging.getLogger("pratifalan.llm")

PROVIDERS = {
    "openrouter": ("https://openrouter.ai/api/v1", "openrouter_api_key"),
    "openai": ("https://api.openai.com/v1", "openai_api_key"),
    "deepseek": ("https://api.deepseek.com/v1", "deepseek_api_key"),
    "kimi": ("https://api.moonshot.ai/v1", "kimi_api_key"),
    "xai": ("https://api.x.ai/v1", "xai_api_key"),
    "nanogpt": ("https://nano-gpt.com/api/v1", "nanogpt_api_key"),
}
ROLES = ("router", "planner", "vision", "translator")


class LLMUnavailable(RuntimeError):
    """No configured provider could serve the request (or the app is in demo mode)."""


@dataclass
class LLMResult:
    text: str
    tool_calls: list[dict]
    provider: str
    model: str
    latency_ms: int
    raw: dict
    parsed: Any = None


def _role_chain(role: str) -> list[tuple[str, str]]:
    s = get_settings()
    spec = getattr(s, f"llm_{role}_model", "") or ""
    order = [p.strip() for p in s.llm_provider_order.split(",") if p.strip()]
    chain = []
    for item in spec.split(","):
        item = item.strip()
        if ":" not in item:
            continue
        prov, model = item.split(":", 1)
        prov = prov.strip().lower()
        if prov in PROVIDERS and (not order or prov in order):
            key = getattr(s, PROVIDERS[prov][1], "")
            if key:
                chain.append((prov, model.strip()))
    chain.sort(key=lambda pm: order.index(pm[0]) if pm[0] in order else 99)
    return chain


def available(role: str) -> bool:
    return get_settings().live and bool(_role_chain(role))


def image_part(data: bytes, mime: str = "image/jpeg") -> dict:
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}}


# Reasoning models spend hidden "thinking" tokens out of max_tokens; too small a budget returns an
# empty or cut-off answer (finish_reason "length"). Each role gets at least this many tokens.
ROLE_MIN_TOKENS = {"router": 300, "planner": 800, "vision": 1500, "translator": 800}


def _is_openai_reasoning(model: str) -> bool:
    """Direct OpenAI reasoning families (gpt-5*, o1/o3/o4*) take max_completion_tokens, not max_tokens."""
    m = model.lower()
    return m.startswith("gpt-5") or bool(re.match(r"o\d", m))


def build_body(prov: str, model: str, messages: list[dict], tools: list[dict] | None, json_mode: bool,
               temperature: float, max_tokens: int) -> dict[str, Any]:
    """Provider-specific request body (pure function, unit-tested)."""
    body: dict[str, Any] = {"model": model, "messages": messages}
    if prov == "openai" and _is_openai_reasoning(model):
        body["max_completion_tokens"] = max_tokens
        body["reasoning_effort"] = "low"  # these models reject a custom temperature
    else:
        body["max_tokens"] = max_tokens
        body["temperature"] = temperature
    if prov == "openrouter" and not model.lower().startswith("anthropic/"):
        # OpenRouter's unified reasoning switch: think a little, never return the reasoning text.
        # (Not for Anthropic models: their thinking budget must be >= 1024 and below max_tokens.)
        body["reasoning"] = {"effort": "low", "exclude": True}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    if json_mode and prov in ("openai", "openrouter", "deepseek"):
        body["response_format"] = {"type": "json_object"}
    return body


class LLMClient:
    def __init__(self, timeout_s: float | None = None) -> None:
        self.timeout = timeout_s or get_settings().llm_timeout_s

    def chat(
        self,
        role: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 900,
        parse: Callable[[str], Any] | None = None,
    ) -> LLMResult:
        """Try each ``provider:model`` of the role in order. A provider counts as failed (and the next
        one is tried) on HTTP errors, timeouts, an answer cut off by the token limit
        (finish_reason "length"), an empty answer without tool calls, or - with ``parse`` - an
        answer that ``parse`` rejects. Failures are logged at WARNING without any content."""
        if not get_settings().live:
            raise LLMUnavailable("APP_MODE=demo: live LLM calls are disabled (fixtures/templates are used)")
        chain = _role_chain(role)
        if not chain:
            raise LLMUnavailable(f"No provider configured for role '{role}'. Set LLM_{role.upper()}_MODEL in .env")
        s = get_settings()
        max_tokens = max(max_tokens, ROLE_MIN_TOKENS.get(role, 0))
        errors = []
        for prov, model in chain:
            base, key_attr = PROVIDERS[prov]
            body = build_body(prov, model, messages, tools, json_mode, temperature, max_tokens)
            headers = {"Authorization": f"Bearer {getattr(s, key_attr)}"}
            if prov == "openrouter":
                headers |= {"HTTP-Referer": "https://pratifalan.duckdns.org", "X-Title": "Pratifalan"}
            t0 = time.time()
            try:
                r = httpx.post(f"{base}/chat/completions", json=body, headers=headers, timeout=self.timeout)
                if r.status_code >= 400:
                    raise RuntimeError(f"HTTP {r.status_code}")
                data = r.json()
                res = parse_response(data, prov, model, int((time.time() - t0) * 1000))
                if parse is not None:
                    try:
                        res.parsed = parse(res.text)
                    except (ValueError, TypeError, KeyError) as exc:
                        raise RuntimeError(f"unparseable answer ({type(exc).__name__})") from None
                return res
            except Exception as exc:  # noqa: BLE001 - fall through to the next provider
                log.warning("llm %s/%s failed for role %s: %s", prov, model, role, str(exc)[:160])
                errors.append(f"{prov}:{model}: {str(exc)[:120]}")
        raise LLMUnavailable("; ".join(errors))

    def json(self, role: str, messages: list[dict], **kw: Any) -> tuple[dict, LLMResult]:
        """Chat in JSON mode; a reply that is not a JSON object falls through to the next provider."""
        res = self.chat(role, messages, json_mode=True, parse=_parse_object, **kw)
        return res.parsed, res


def parse_response(data: dict, prov: str, model: str, latency_ms: int) -> LLMResult:
    """Chat Completions JSON -> LLMResult; raises on a truncated or empty answer."""
    choice = data["choices"][0]
    msg = choice.get("message") or {}
    text = msg.get("content") or ""
    if isinstance(text, list):
        text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
    calls = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", {})
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        calls.append({"id": tc.get("id"), "name": fn.get("name"), "args": args if isinstance(args, dict) else {}})
    if choice.get("finish_reason") == "length" and not calls:
        raise RuntimeError("answer cut off by the token limit (finish_reason=length)")
    if not str(text).strip() and not calls:
        raise RuntimeError("empty answer")
    return LLMResult(str(text), calls, prov, model, latency_ms, data)


def _parse_object(text: str) -> dict:
    out = parse_json(text)
    if not isinstance(out, dict):
        raise ValueError("JSON answer is not an object")
    return out


def parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start: end + 1]
    return json.loads(text)
