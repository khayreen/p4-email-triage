"""Load emails from .eml files or a JSONL file (one {"subject","body","sender"} per line)."""
from __future__ import annotations

import json
from email import message_from_bytes, policy
from pathlib import Path
from typing import Iterator

from ..schemas import EmailIn


def from_eml_bytes(raw: bytes) -> EmailIn:
    msg = message_from_bytes(raw, policy=policy.default)
    part = msg.get_body(preferencelist=("plain", "html"))
    body = part.get_content() if part else ""
    return EmailIn(subject=str(msg["subject"] or "")[:500], body=(body.strip() or "(empty)")[:20_000], sender=str(msg["from"] or "") or None)


def load(path: str | Path) -> Iterator[EmailIn]:
    path = Path(path)
    if path.is_dir():
        for file in sorted(path.glob("*.eml")):
            yield from_eml_bytes(file.read_bytes())
    elif path.suffix == ".eml":
        yield from_eml_bytes(path.read_bytes())
    else:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    row = json.loads(line)
                    yield EmailIn(subject=row.get("subject", ""), body=row["body"], sender=row.get("sender"))
