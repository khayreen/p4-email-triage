"""The HTTP client, tested against a stubbed transport (no network, no key)."""
import httpx
import pytest

from app import llm
from app.llm import LLMError, OpenAICompatProvider


def stub(monkeypatch, responses):
    calls = []

    def fake_post(url, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers})
        item = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return httpx.Response(item[0], json=item[1], headers=item[2] if len(item) > 2 else None)

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    return calls


OK = (200, {"choices": [{"message": {"content": '{"a": 1}'}}]})


def test_request_shape(monkeypatch):
    calls = stub(monkeypatch, [OK])
    out = OpenAICompatProvider("https://api.example/v1/", "k123", "m1").complete("SYS", "USER")
    assert out == '{"a": 1}'
    call = calls[0]
    assert call["url"] == "https://api.example/v1/chat/completions"
    assert call["headers"] == {"Authorization": "Bearer k123"}
    assert call["json"]["model"] == "m1" and call["json"]["temperature"] == 0
    assert call["json"]["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in call["json"]["messages"]] == ["system", "user"]


def test_no_auth_header_without_key(monkeypatch):
    calls = stub(monkeypatch, [OK])
    OpenAICompatProvider("http://localhost:11434/v1", "", "m").complete("s", "u")
    assert calls[0]["headers"] == {}


def test_rate_limit_and_server_errors_are_retried(monkeypatch):
    calls = stub(monkeypatch, [(429, {}, {"retry-after": "1"}), (503, {}), OK])
    assert OpenAICompatProvider("http://x", "k", "m").complete("s", "u") == '{"a": 1}'
    assert len(calls) == 3


def test_auth_error_is_not_retried_and_hides_the_key(monkeypatch):
    calls = stub(monkeypatch, [(401, {"error": "bad key k123"})])
    with pytest.raises(LLMError) as exc:
        OpenAICompatProvider("http://x", "k123", "m").complete("s", "u")
    assert len(calls) == 1 and "k123" not in str(exc.value)


def test_gives_up_after_max_retries(monkeypatch):
    calls = stub(monkeypatch, [httpx.ConnectError("down")])
    with pytest.raises(LLMError):
        OpenAICompatProvider("http://x", "k", "m").complete("s", "u")
    assert len(calls) == 3


def test_unexpected_body_is_an_error(monkeypatch):
    stub(monkeypatch, [(200, {"nope": True})])
    with pytest.raises(LLMError):
        OpenAICompatProvider("http://x", "k", "m").complete("s", "u")
