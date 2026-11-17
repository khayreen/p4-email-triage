"""Prompt-injection screening for inbound email, and checks on model output.

Heuristics cannot catch every attack. They are one layer: a hit never blocks
the email, it forces the item to human review. The stronger defences are
structural (see classifier.py): the email is passed as delimited data, the
output is a closed schema, and nothing is ever sent without approval.
"""
from __future__ import annotations

import re
import unicodedata

_PATTERNS = [
    r"ignore (?:all |any |the )?(?:previous|prior|above|earlier) (?:instructions|prompts|rules|messages)",
    r"disregard (?:all |any |the |your )?(?:previous|prior|above|system) (?:instructions|prompts?|rules)",
    r"forget (?:everything|all|your) (?:above|previous|instructions|rules)",
    r"(?:you are|act as|pretend to be) (?:now )?(?:a|an|the)? ?(?:dan|developer mode|unrestricted|jailbroken)",
    r"(?:new|updated|override) (?:system )?(?:instructions?|prompt|rules?)\s*:",
    r"system\s*(?:prompt|message|override)",
    r"(?:reveal|print|show|repeat|output) (?:me )?(?:your|the) (?:system )?(?:prompt|instructions|rules)",
    r"(?:classify|label|mark|categori[sz]e) this (?:email|message)? ?as",
    r"set (?:the )?(?:urgency|category|priority|confidence) to",
    r"(?:respond|reply|answer) (?:only )?with (?:the )?(?:following|exactly)",
    r"</?(?:system|assistant|instructions?|email)>",
    r"\[/?(?:system|inst|assistant)\]",
    r"abaikan (?:semua )?arahan",  # Malay: "ignore (all) instructions"
    r"do not (?:flag|escalate|review)",
    r"(?:approve|refund|transfer|waive) .{0,40}(?:automatically|immediately without|without (?:review|approval|verification))",
]
_INJECTION = re.compile("|".join(f"(?:{p})" for p in _PATTERNS), re.IGNORECASE)
_ZERO_WIDTH = re.compile(r"[​-‏⁠-⁤﻿]")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)


def normalise(text: str) -> str:
    """Undo common obfuscation: zero-width characters, odd unicode forms, spacing."""
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH.sub("", text)
    return re.sub(r"\s+", " ", text)


def injection_suspected(text: str) -> bool:
    return bool(_INJECTION.search(normalise(text)))


def neutralise_delimiters(text: str) -> str:
    """Stop an email from closing our data block and starting its own section."""
    return text.replace("<", "‹").replace(">", "›")


def reply_problems(reply: str) -> list[str]:
    """Reasons a drafted reply must not go out as written."""
    problems = []
    if _URL.search(reply):
        problems.append("reply_contains_link")
    if re.search(r"\[(?:IC|CARD|PHONE|ACCOUNT|PASSPORT|EMAIL)\]", reply):
        problems.append("reply_contains_placeholder")
    if re.search(r"\b(?:password|pin|otp|tac)\b.{0,40}\b(?:send|share|provide|reply with)\b", reply, re.I) or re.search(
        r"\b(?:send|share|provide|reply with)\b.{0,40}\b(?:password|pin|otp|tac)\b", reply, re.I
    ):
        problems.append("reply_requests_credentials")
    return problems
