"""Streaming client for any OpenAI-compatible chat endpoint (llama-server, Ollama, vLLM, ...)."""
import json
import os
from collections.abc import AsyncIterator

import httpx

URL = os.environ.get("PP_LLM_URL", "http://127.0.0.1:8080/v1")
MODEL = os.environ.get("PP_LLM_MODEL", "local")
KEY = os.environ.get("PP_LLM_API_KEY", "")
# Keeps reasoning models fast for live turns; harmless for models that ignore it.
EXTRA = json.loads(os.environ.get("PP_LLM_EXTRA", '{"chat_template_kwargs": {"reasoning_effort": "low", "enable_thinking": false}}'))


def _body(messages: list[dict], stream: bool, max_tokens: int) -> dict:
    return {"model": MODEL, "messages": messages, "stream": stream, "max_tokens": max_tokens, **EXTRA}


def _headers() -> dict:
    return {"Authorization": f"Bearer {KEY}"} if KEY else {}


async def stream(messages: list[dict], max_tokens: int = 300) -> AsyncIterator[str]:
    async with httpx.AsyncClient(timeout=None) as c:
        async with c.stream("POST", f"{URL}/chat/completions", json=_body(messages, True, max_tokens), headers=_headers()) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data: ") or line.endswith("[DONE]"):
                    continue
                delta = json.loads(line[6:])["choices"][0]["delta"].get("content")
                if delta:
                    yield delta


async def complete(messages: list[dict], max_tokens: int = 1500) -> str:
    async with httpx.AsyncClient(timeout=None) as c:
        r = await c.post(f"{URL}/chat/completions", json=_body(messages, False, max_tokens), headers=_headers())
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""
