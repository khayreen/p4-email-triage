"""FastAPI service: triage an email, queue it, and let a human approve the reply.

There is deliberately no "send" endpoint. Approving records the final reply;
sending stays a human action in the mail client.
"""
from __future__ import annotations

import hmac
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse

from . import config
from .classifier import triage
from .llm import OpenAICompatProvider, Provider
from .pii import install_log_masking
from .schemas import ApproveIn, EmailIn, QueueItem, RejectIn
from .store import STATUSES, Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
install_log_masking()
log = logging.getLogger("triage.api")

_UI = (Path(__file__).parent / "review.html").read_text(encoding="utf-8")


def create_app(settings: config.Settings | None = None, provider: Provider | None = None) -> FastAPI:
    settings = settings or config.load()
    store = Store(settings.db_path)
    if provider is None and settings.provider != "baseline":
        if settings.api_key or settings.provider == "ollama":
            provider = OpenAICompatProvider(settings.base_url, settings.api_key, settings.model, settings.timeout_s)
        else:
            log.warning("no API key for provider '%s'; using keyword baseline only", settings.provider)

    def require_key(x_api_key: str = Header(default="")) -> None:
        expected = settings.service_api_key
        if expected and not hmac.compare_digest(x_api_key.encode(), expected.encode()):
            raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")

    app = FastAPI(
        title="Email & Complaint Triage",
        version="1.0.0",
        description="Classifies bank customer emails and drafts replies for human approval.",
    )
    guarded = [Depends(require_key)]

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "classifier": "llm" if provider else "baseline",
            "provider": settings.provider if provider else None,
            "model": provider.model if provider else None,
        }

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def review_ui() -> str:
        return _UI

    @app.post("/triage", dependencies=guarded, status_code=201)
    def triage_email(email: EmailIn) -> QueueItem:
        result = triage(email, provider, settings.review_threshold)
        item = store.get(store.add(email, result))
        assert item is not None
        return item

    @app.get("/queue", dependencies=guarded)
    def list_queue(status: str | None = Query(default=None), limit: int = Query(default=100, ge=1, le=500)) -> list[QueueItem]:
        if status is not None and status not in STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of {STATUSES}")
        return store.list(status, limit)

    @app.get("/queue/{item_id}", dependencies=guarded)
    def get_item(item_id: int) -> QueueItem:
        item = store.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="item not found")
        return item

    def _decide(item_id: int, status: str, reply: str | None, note: str | None) -> QueueItem:
        if store.get(item_id) is None:
            raise HTTPException(status_code=404, detail="item not found")
        item = store.decide(item_id, status, reply, note)
        if item is None:
            raise HTTPException(status_code=409, detail="item has already been reviewed")
        return item

    @app.post("/queue/{item_id}/approve", dependencies=guarded)
    def approve(item_id: int, body: ApproveIn | None = None) -> QueueItem:
        current = store.get(item_id)
        if current is None:
            raise HTTPException(status_code=404, detail="item not found")
        reply = (body.reply if body and body.reply else current.result.suggested_reply).strip()
        if not reply:
            raise HTTPException(status_code=422, detail="no reply to approve; provide one")
        return _decide(item_id, "approved", reply, None)

    @app.post("/queue/{item_id}/reject", dependencies=guarded)
    def reject(item_id: int, body: RejectIn | None = None) -> QueueItem:
        return _decide(item_id, "rejected", None, body.reason if body else "")

    @app.get("/stats", dependencies=guarded)
    def stats() -> dict:
        return store.stats()

    return app

