from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app import baseline
from app.classifier import triage
from app.ingest import files, gmail
from app.llm import LLMError
from app.main import create_app
from app.schemas import Category, EmailIn, Urgency

from .conftest import GOOD, FakeProvider, make_settings


# --- pipeline ---------------------------------------------------------------------

def test_valid_output_is_accepted(provider):
    result = triage(EmailIn(subject="Statement", body="Please send my statement."), provider)
    assert (result.category, result.urgency, result.classifier) == (Category.account_services, Urgency.medium, "llm")
    assert not result.needs_review and result.model == "fake-model"


def test_fenced_json_is_accepted():
    result = triage(EmailIn(body="hi"), FakeProvider("```json\n" + json.dumps(GOOD) + "\n```"))
    assert result.classifier == "llm"


def test_malformed_output_is_retried_once():
    provider = FakeProvider("not json", json.dumps(GOOD))
    assert triage(EmailIn(body="hi"), provider).classifier == "llm"
    assert len(provider.calls) == 2


def test_llm_outage_falls_back_to_baseline_with_review():
    provider = FakeProvider(LLMError("HTTP 503"))
    result = triage(EmailIn(subject="Loan", body="What is the early settlement amount for my loan?"), provider)
    assert result.classifier == "baseline" and result.category is Category.financing
    assert result.needs_review and result.review_reasons == ["llm_unavailable"]
    assert len(provider.calls) == 1  # outages are not retried here; the client already did


def test_low_confidence_high_urgency_and_fraud_go_to_review():
    low = triage(EmailIn(body="hi"), FakeProvider(json.dumps(dict(GOOD, confidence=0.4))))
    assert low.review_reasons == ["low_confidence"]
    fraud = triage(EmailIn(body="hi"), FakeProvider(json.dumps(dict(GOOD, category="fraud_security", urgency="high"))))
    assert set(fraud.review_reasons) == {"high_urgency", "fraud_case"}


def test_baseline_examples():
    assert baseline.classify("Scam", "I did not make this transfer, please block my account")[0:2] == (Category.fraud_security, Urgency.high)
    assert baseline.classify("", "zzz")[0] is Category.other


# --- API --------------------------------------------------------------------------

def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "classifier": "llm", "provider": "groq", "model": "fake-model"}


def test_triage_then_approve_flow(client):
    item = client.post("/triage", json={"subject": "Statement", "body": "Please send it", "sender": "a@b.com"}).json()
    assert item["status"] == "pending" and item["id"] == 1
    assert [i["id"] for i in client.get("/queue", params={"status": "pending"}).json()] == [1]

    approved = client.post("/queue/1/approve", json={"reply": "Edited by a human."}).json()
    assert approved["status"] == "approved" and approved["final_reply"] == "Edited by a human."
    assert client.get("/queue", params={"status": "pending"}).json() == []
    assert client.post("/queue/1/approve").status_code == 409  # cannot be decided twice
    assert client.post("/queue/1/reject").status_code == 409


def test_approve_without_body_uses_the_draft(client):
    client.post("/triage", json={"body": "hello"})
    assert client.post("/queue/1/approve").json()["final_reply"] == GOOD["suggested_reply"]


def test_cannot_approve_an_empty_draft(tmp_path):
    client = TestClient(create_app(make_settings(tmp_path), FakeProvider(LLMError("down"))))
    client.post("/triage", json={"body": "hello"})
    assert client.post("/queue/1/approve").status_code == 422
    assert client.post("/queue/1/approve", json={"reply": "Written by the agent."}).status_code == 200


def test_reject_flow_and_stats(client):
    client.post("/triage", json={"body": "one"})
    client.post("/triage", json={"body": "two"})
    rejected = client.post("/queue/2/reject", json={"reason": "spam"}).json()
    assert rejected["status"] == "rejected" and rejected["review_note"] == "spam" and rejected["final_reply"] is None
    stats = client.get("/stats").json()
    assert stats["total"] == 2 and stats["by_status"] == {"pending": 1, "rejected": 1}


def test_validation_and_not_found(client):
    assert client.post("/triage", json={"subject": "no body"}).status_code == 422
    assert client.post("/triage", json={"body": ""}).status_code == 422
    assert client.post("/triage", json={"body": "x" * 20_001}).status_code == 422
    assert client.get("/queue/99").status_code == 404
    assert client.post("/queue/99/approve").status_code == 404
    assert client.get("/queue", params={"status": "bogus"}).status_code == 422


def test_api_key_is_enforced_when_set(tmp_path, provider):
    client = TestClient(create_app(make_settings(tmp_path, service_api_key="s3cret"), provider))
    assert client.post("/triage", json={"body": "hi"}).status_code == 401
    assert client.get("/queue", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post("/triage", json={"body": "hi"}, headers={"X-API-Key": "s3cret"}).status_code == 201
    assert client.get("/health").status_code == 200  # health stays open for monitoring


def test_no_key_configured_means_baseline_mode(tmp_path):
    client = TestClient(create_app(make_settings(tmp_path)))
    assert client.get("/health").json()["classifier"] == "baseline"
    item = client.post("/triage", json={"subject": "Lost card", "body": "My card was stolen, block it"}).json()
    assert item["result"]["classifier"] == "baseline" and item["result"]["needs_review"]


# --- ingestion --------------------------------------------------------------------

def test_eml_parsing():
    raw = b"From: Ali <ali@example.com>\r\nSubject: Hello\r\nContent-Type: text/plain\r\n\r\nBody text here.\r\n"
    email = files.from_eml_bytes(raw)
    assert (email.subject, email.body, email.sender) == ("Hello", "Body text here.", "Ali <ali@example.com>")


def test_jsonl_loading(tmp_path):
    path = tmp_path / "in.jsonl"
    path.write_text('{"subject":"a","body":"b"}\n\n{"body":"c","sender":"x@y.z"}\n')
    assert [(e.subject, e.body, e.sender) for e in files.load(path)] == [("a", "b", None), ("", "c", "x@y.z")]


def test_gmail_message_parsing():
    b64 = lambda s: __import__("base64").urlsafe_b64encode(s.encode()).decode().rstrip("=")
    message = {
        "snippet": "snip",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [{"name": "Subject", "value": "Card"}, {"name": "From", "value": "x@y.z"}],
            "parts": [
                {"mimeType": "text/html", "body": {"data": b64("<p>html</p>")}},
                {"mimeType": "text/plain", "body": {"data": b64("plain body")}},
            ],
        },
    }
    email = gmail.parse_message(message)
    assert (email.subject, email.body, email.sender) == ("Card", "plain body", "x@y.z")
    assert gmail.parse_message({"snippet": "only snippet", "payload": {}}).body == "only snippet"
