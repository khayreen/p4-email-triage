"""Keyword baseline. It needs no API key, so it serves two jobs:

1. The comparison point for the LLM's accuracy ("is the model worth its cost?").
2. The fallback when the LLM is unavailable or returns invalid output.
"""
from __future__ import annotations

import re

from .schemas import Category, Urgency

_KEYWORDS: dict[Category, list[str]] = {
    Category.fraud_security: [
        "fraud", "scam", "unauthorised", "unauthorized", "did not make", "didn't make", "never made",
        "hacked", "phishing", "suspicious", "stolen", "otp", "tac", "macau", "mule", "penipuan",
        "tidak sah", "ditipu", "scammer", "compromised", "not me", "bukan saya",
    ],
    Category.complaint: [
        "complain", "complaint", "unacceptable", "disappointed", "rude", "terrible", "worst",
        "waited", "poor service", "escalate", "bank negara", "bnm", "aduan", "kecewa", "tidak puas",
        "frustrated", "ridiculous", "no one", "nobody", "still not", "third time", "appalling",
    ],
    Category.card_services: [
        "credit card", "debit card", "card", "kad", "annual fee", "credit limit", "replacement",
        "cashback", "reward points", "pin", "contactless", "activate", "atm swallowed", "expired",
    ],
    Category.financing: [
        "loan", "financing", "pembiayaan", "pinjaman", "mortgage", "instalment", "installment",
        "settlement", "moratorium", "restructure", "reschedule", "hire purchase", "asb", "tenure",
        "profit rate", "interest rate", "early settlement", "arrears", "tunggakan", "home financing",
    ],
    Category.account_services: [
        "account", "akaun", "statement", "penyata", "address", "update my", "online banking",
        "password", "login", "log in", "transfer limit", "duitnow", "savings", "current account",
        "dormant", "close my", "joint account", "fixed deposit", "nominee", "kemaskini",
    ],
    Category.other: [
        "unsubscribe", "newsletter", "congratulations you", "lottery", "seo", "partnership",
        "job", "vacancy", "internship", "sponsorship", "thank you", "terima kasih", "great service",
        "opening hours", "invoice attached", "webinar", "survey", "promotion", "suggestion",
    ],
}
# Stronger signals count more, so "card" alone does not beat "unauthorised".
_WEIGHT = {
    Category.fraud_security: 3.0,
    Category.complaint: 2.0,
    Category.financing: 2.0,
    Category.card_services: 1.5,
    Category.account_services: 1.0,
    Category.other: 1.5,
}
_HIGH = [
    "urgent", "immediately", "segera", "asap", "right now", "today", "locked", "blocked", "frozen",
    "stolen", "lost my card", "hilang", "police", "polis", "legal", "lawyer", "bank negara",
    "all my savings", "salary", "cannot access", "tidak boleh akses", "emergency",
]
_LOW = ["thank", "terima kasih", "suggestion", "feedback", "newsletter", "unsubscribe", "just wondering", "no rush"]


def classify(subject: str, body: str) -> tuple[Category, Urgency, float]:
    text = f"{subject}\n{body}".lower()
    scores = {
        cat: _WEIGHT[cat] * sum(1 for kw in words if re.search(rf"(?<!\w){re.escape(kw)}", text))
        for cat, words in _KEYWORDS.items()
    }
    best = max(scores, key=lambda c: scores[c])
    total = sum(scores.values())
    if scores[best] == 0:
        return Category.other, Urgency.low, 0.2
    confidence = round(min(0.9, 0.35 + 0.55 * scores[best] / total), 2)

    if best is Category.fraud_security or any(w in text for w in _HIGH):
        urgency = Urgency.high
    elif best is Category.other or any(w in text for w in _LOW):
        urgency = Urgency.low
    else:
        urgency = Urgency.medium
    return best, urgency, confidence
