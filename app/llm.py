"""One client for every OpenAI-compatible chat API (Groq, Gemini, OpenRouter, Ollama)."""
from __future__ import annotations

import time
from typing import Protocol

import httpx


class LLMError(RuntimeError):
    pass


class Provider(Protocol):
    model: str

    def complete(self, system: str, user: str) -> str: ...


class OpenAICompatProvider:
    def __init__(self, base_url: str, api_key: str, model: str, timeout_s: float = 30, max_retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s
        self.max_retries = max_retries

    def complete(self, system: str, user: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        last = "no attempt made"
        for attempt in range(self.max_retries):
            try:
                r = httpx.post(
                    f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=self.timeout_s
                )
            except httpx.HTTPError as exc:
                last = f"network error: {type(exc).__name__}"
            else:
                if r.status_code == 200:
                    try:
                        return r.json()["choices"][0]["message"]["content"] or ""
                    except (KeyError, IndexError, ValueError) as exc:
                        raise LLMError("unexpected response shape") from exc
                last = f"HTTP {r.status_code}"
                # Only rate limits and server errors are worth retrying.
                if r.status_code != 429 and r.status_code < 500:
                    break
                retry_after = r.headers.get("retry-after", "")
                if retry_after.replace(".", "", 1).isdigit():
                    time.sleep(min(float(retry_after), 30))
                    continue
            time.sleep(2**attempt)
        raise LLMError(f"LLM call failed: {last}")
