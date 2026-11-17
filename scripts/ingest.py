"""Triage a batch of emails into the review queue.

  python -m scripts.ingest --path data/sample_inbox.jsonl
  python -m scripts.ingest --path ./eml_folder
  python -m scripts.ingest --gmail --query "label:triage-test"
"""
from __future__ import annotations

import argparse
import time

from app import config
from app.classifier import triage
from app.ingest import files
from app.llm import LLMError, OpenAICompatProvider, explain
from app.pii import install_log_masking
from app.store import Store


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", help=".jsonl file, .eml file, or folder of .eml files")
    ap.add_argument("--gmail", action="store_true", help="read from Gmail (read-only scope)")
    ap.add_argument("--query", default="newer_than:7d", help="Gmail search query")
    ap.add_argument("--max", type=int, default=20)
    ap.add_argument("--sleep", type=float, default=2.2, help="seconds between LLM calls (free tiers allow ~30/min)")
    args = ap.parse_args()
    if bool(args.path) == args.gmail:
        ap.error("give exactly one of --path or --gmail")

    install_log_masking()
    settings = config.load()
    provider = None
    if settings.provider != "baseline" and (settings.api_key or settings.provider == "ollama"):
        provider = OpenAICompatProvider(settings.base_url, settings.api_key, settings.model, settings.timeout_s)
    store = Store(settings.db_path)

    if args.gmail:
        from app.ingest import gmail
        emails = gmail.fetch(args.query, args.max)
    else:
        emails = files.load(args.path)

    if provider:
        try:
            provider.complete("Reply with the JSON object {\"ok\": true}.", "ping")
        except LLMError as exc:
            raise SystemExit(f"The LLM is not reachable.\n  {explain(exc)}")

    count = 0
    for email in emails:
        result = triage(email, provider, settings.review_threshold)
        item_id = store.add(email, result)
        print(f"#{item_id:<4} {result.category.value:<17} {result.urgency.value:<7} review={result.needs_review}")
        count += 1
        if provider:
            time.sleep(args.sleep)
    print(f"\n{count} email(s) queued in {settings.db_path} using {'LLM ' + settings.model if provider else 'keyword baseline'}.")


if __name__ == "__main__":
    main()
