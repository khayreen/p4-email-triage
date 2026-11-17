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


def test_model_without_json_mode_is_retried_without_it(monkeypatch):
    calls = stub(monkeypatch, [(400, {"error": "response_format not supported"}), OK])
    assert OpenAICompatProvider("http://x", "k", "m").complete("s", "u") == '{"a": 1}'
    assert "response_format" in calls[0]["json"] and "response_format" not in calls[1]["json"]


def test_failures_are_explained_in_plain_words(monkeypatch):
    stub(monkeypatch, [(404, {})])
    with pytest.raises(LLMError) as exc:
        OpenAICompatProvider("http://x", "k", "retired-model").complete("s", "u")
    assert "LLM_MODEL" in llm.explain(exc.value) and "HTTP 404" in llm.explain(exc.value)
    assert llm.explain(LLMError("LLM call failed: network error: ConnectError")) == "LLM call failed: network error: ConnectError"


def test_evaluation_refuses_to_report_when_the_llm_is_unreachable(monkeypatch, tmp_path, capsys):
    import sys

    from eval import run_eval

    stub(monkeypatch, [(404, {})])
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setattr(run_eval, "ROOT", tmp_path)   # would write results here if it wrongly continued
    monkeypatch.setattr(sys, "argv", ["run_eval", "--classifier", "llm", "--data", str(run_eval.Path(__file__).parent.parent / "data" / "emails.jsonl")])
    with pytest.raises(SystemExit) as exc:
        run_eval.main()
    assert "not reachable" in str(exc.value) and "LLM_MODEL" in str(exc.value)
    assert not (tmp_path / "results").exists()
