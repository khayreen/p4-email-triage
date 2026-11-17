"""Data contracts. The LLM must return exactly `LLMOutput`; anything else is rejected."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Category(str, Enum):
    fraud_security = "fraud_security"
    complaint = "complaint"
    account_services = "account_services"
    card_services = "card_services"
    financing = "financing"
    other = "other"


class Urgency(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class EmailIn(BaseModel):
    """An inbound email. `sender` is kept for the human reviewer, never sent to the model."""

    subject: str = Field(default="", max_length=500)
    body: str = Field(min_length=1, max_length=20_000)
    sender: str | None = Field(default=None, max_length=320)


class LLMOutput(BaseModel):
    """The strict schema the model must satisfy. Unknown fields are an error."""

    model_config = ConfigDict(extra="forbid")

    category: Category
    urgency: Urgency
    summary: str = Field(min_length=1, max_length=400)
    suggested_reply: str = Field(min_length=1, max_length=1500)
    confidence: float = Field(ge=0.0, le=1.0)


class TriageResult(BaseModel):
    category: Category
    urgency: Urgency
    summary: str
    suggested_reply: str
    confidence: float
    needs_review: bool
    review_reasons: list[str] = Field(default_factory=list)
    injection_suspected: bool = False
    pii_found: dict[str, int] = Field(default_factory=dict)
    classifier: str = "llm"
    model: str | None = None
    latency_ms: int = 0


class QueueItem(BaseModel):
    id: int
    received_at: str
    sender: str | None
    subject: str
    body: str
    result: TriageResult
    status: str
    final_reply: str | None = None
    review_note: str | None = None
    reviewed_at: str | None = None


class ApproveIn(BaseModel):
    reply: str | None = Field(default=None, max_length=5000)


class RejectIn(BaseModel):
    reason: str = Field(default="", max_length=1000)
