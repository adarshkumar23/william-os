"""WILLIAM OS - Central LLM call helper (H1 fix).

All services should route HTTP calls to external LLMs/APIs through these helpers,
which provide: (a) exponential backoff with jitter on 5xx/timeout/network errors,
(b) a typed error on permanent failure, (c) a single place to observe latency.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class AIError(Exception):
    """Raised when an LLM call permanently fails (all retries exhausted)."""


_DEFAULT_RETRIES = 3
_DEFAULT_TIMEOUT = 30.0


def _backoff(attempt: int) -> float:
    """Exponential backoff + full jitter (AWS-style)."""
    base = 0.5 * (2**attempt)  # 0.5s, 1s, 2s, 4s
    return random.uniform(0, min(base, 8.0))


async def http_post_json(
    url: str,
    *,
    headers: dict[str, str],
    json: dict[str, Any],
    timeout: float = _DEFAULT_TIMEOUT,
    retries: int = _DEFAULT_RETRIES,
) -> dict[str, Any]:
    """POST JSON with retries on transient errors. Returns parsed JSON or raises AIError."""
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=headers, json=json)
            if 500 <= resp.status_code < 600:
                raise httpx.HTTPStatusError(
                    f"server {resp.status_code}", request=resp.request, response=resp
                )
            if resp.status_code >= 400:
                # 4xx is permanent — don't retry
                raise AIError(f"http_{resp.status_code}: {resp.text[:200]}")
            ctype = resp.headers.get("content-type", "")
            if "application/json" not in ctype:
                raise AIError(f"non-json response (content-type={ctype!r})")
            return resp.json()
        except AIError:
            raise  # permanent
        except Exception as exc:
            last_exc = exc
            if attempt >= retries:
                break
            delay = _backoff(attempt)
            logger.warning(
                "ai_call_retry",
                url=url,
                attempt=attempt + 1,
                delay_seconds=round(delay, 2),
                error=str(exc),
            )
            await asyncio.sleep(delay)
    raise AIError(f"retries exhausted: {last_exc}") from last_exc


async def call_gemini(
    *,
    api_key: str,
    model: str,
    prompt: str,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    response_mime_type: str | None = "application/json",
) -> str:
    """Call Gemini generateContent with retries. Returns the text part."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    gen_config: dict[str, Any] = {
        "temperature": temperature,
        "topP": 0.9,
        "maxOutputTokens": max_tokens,
    }
    if response_mime_type:
        gen_config["responseMimeType"] = response_mime_type
    data = await http_post_json(
        url,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen_config},
    )
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise AIError(f"unexpected gemini response shape: {exc}") from exc


async def call_llm_json_compat(
    *,
    provider: str,
    model: str,
    api_key: str,
    messages: list[dict[str, str]],
    max_tokens: int = 512,
    temperature: float = 0.2,
    base_url: str = "",
    app_name: str = "",
) -> str:
    """Call an OpenAI-compatible chat endpoint (OpenRouter/OpenAI/etc.) with retries."""
    if provider == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": base_url or "http://localhost",
            "X-Title": app_name or "William OS",
        }
    elif provider == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    else:
        raise AIError(f"unsupported provider: {provider}")

    data = await http_post_json(
        url,
        headers=headers,
        json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
    )
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise AIError(f"unexpected chat response shape: {exc}") from exc
