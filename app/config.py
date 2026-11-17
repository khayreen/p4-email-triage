"""Settings come from environment variables. Changing LLM provider is one line."""
from __future__ import annotations

import os
from dataclasses import dataclass

# Every provider here speaks the OpenAI-compatible chat API, so one client covers all.
PRESETS: dict[str, dict[str, str]] = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "model": "openai/gpt-oss-120b",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_env": "GEMINI_API_KEY",
        "model": "gemini-2.5-flash",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "key_env": "",
        "model": "llama3.2",
    },
}


@dataclass(frozen=True)
class Settings:
    provider: str
    base_url: str
    api_key: str
    model: str
    db_path: str
    service_api_key: str
    review_threshold: float
    timeout_s: float


def _read_dotenv(path: str = ".env") -> None:
    """Minimal .env reader so no extra dependency is needed. Real env vars win."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load() -> Settings:
    _read_dotenv()
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    if provider not in PRESETS and provider != "baseline":
        raise ValueError(f"LLM_PROVIDER must be one of {sorted(PRESETS)} or 'baseline'")
    preset = PRESETS.get(provider, {"base_url": "", "key_env": "", "model": ""})
    return Settings(
        provider=provider,
        base_url=os.getenv("LLM_BASE_URL", preset["base_url"]),
        api_key=os.getenv(preset["key_env"], "") if preset["key_env"] else "",
        model=os.getenv("LLM_MODEL", preset["model"]),
        db_path=os.getenv("TRIAGE_DB", "triage.db"),
        service_api_key=os.getenv("SERVICE_API_KEY", ""),
        review_threshold=float(os.getenv("REVIEW_THRESHOLD", "0.75")),
        timeout_s=float(os.getenv("LLM_TIMEOUT_S", "30")),
    )
