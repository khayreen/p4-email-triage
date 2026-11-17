from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import create_app

GOOD = {
    "category": "account_services",
    "urgency": "medium",
    "summary": "Customer wants their statement.",
    "suggested_reply": "Thank you for contacting us. An agent will assist you shortly.",
    "confidence": 0.92,
}


class FakeProvider:
    """Stands in for the LLM and records everything that would leave the service."""

    model = "fake-model"

    def __init__(self, *responses):
        self.responses = list(responses) or [json.dumps(GOOD)]
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        response = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        if isinstance(response, Exception):
            raise response
        return response

    @property
    def sent(self) -> str:
        return "\n".join(f"{s}\n{u}" for s, u in self.calls)


def make_settings(tmp_path, **overrides) -> config.Settings:
    values = dict(
        provider="groq", base_url="http://unused", api_key="", model="fake-model",
        db_path=str(tmp_path / "test.db"), service_api_key="", review_threshold=0.75, timeout_s=5,
    )
    values.update(overrides)
    return config.Settings(**values)


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def client(tmp_path, provider):
    return TestClient(create_app(make_settings(tmp_path), provider))
