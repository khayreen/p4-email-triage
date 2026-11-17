"""Read-only Gmail ingestion.

Uses the narrowest scope that works (gmail.readonly): this service can read
mail but cannot send, delete or modify it. Point it at a dedicated test inbox
holding synthetic emails. Never connect a mailbox with real customer data.

Setup (one time):
  1. Google Cloud console -> create a project -> enable the Gmail API.
  2. Create an OAuth client ID of type "Desktop app"; download it as credentials.json.
  3. pip install -r requirements-gmail.txt
  4. python -m scripts.ingest --gmail --query "label:triage-test newer_than:7d"
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Iterator

from ..schemas import EmailIn

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _find_text(payload: dict) -> str:
    """Depth-first search for the first text/plain part, falling back to text/html."""
    html = ""
    stack = [payload]
    while stack:
        part = stack.pop(0)
        data = part.get("body", {}).get("data")
        mime = part.get("mimeType", "")
        if data and mime == "text/plain":
            return _decode(data)
        if data and mime == "text/html" and not html:
            html = _decode(data)
        stack.extend(part.get("parts", []))
    return html


def parse_message(message: dict) -> EmailIn:
    """Convert a Gmail API `users.messages.get(format='full')` response."""
    payload = message.get("payload", {})
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
    body = _find_text(payload).strip() or message.get("snippet", "") or "(empty)"
    return EmailIn(subject=headers.get("subject", "")[:500], body=body[:20_000], sender=headers.get("from") or None)


def fetch(query: str = "newer_than:7d", max_results: int = 20, credentials: str = "credentials.json", token: str = "token.json") -> Iterator[EmailIn]:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(token, SCOPES) if Path(token).exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = InstalledAppFlow.from_client_secrets_file(credentials, SCOPES).run_local_server(port=0)
        Path(token).write_text(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    listing = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    for ref in listing.get("messages", []):
        yield parse_message(service.users().messages().get(userId="me", id=ref["id"], format="full").execute())
