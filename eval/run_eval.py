"""Measure triage accuracy against the labelled test set.

  python -m eval.run_eval --classifier baseline          # no API key needed
  python -m eval.run_eval --classifier llm               # uses LLM_PROVIDER + its API key

Writes results/<classifier>.json and results/<classifier>.md.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

from app import config
from app.classifier import triage
from app.llm import LLMError, OpenAICompatProvider, explain
from app.schemas import Category, EmailIn, Urgency

ROOT = Path(__file__).resolve().parent.parent
CATS = [c.value for c in Category]
URGS = [u.value for u in Urgency]


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def per_class(pairs: list[tuple[str, str]], labels: list[str]) -> dict[str, dict[str, float]]:
    out = {}
    for label in labels:
        tp = sum(1 for t, p in pairs if t == label and p == label)
        fp = sum(1 for t, p in pairs if t != label and p == label)
        fn = sum(1 for t, p in pairs if t == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        out[label] = {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3), "support": tp + fn}
    return out


def evaluate(rows: list[dict], provider, sleep: float) -> dict:
    cat_pairs, urg_pairs, misses, latencies, predictions = [], [], [], [], []
    fallbacks = 0
    for i, row in enumerate(rows, 1):
        result = triage(EmailIn(subject=row["subject"], body=row["body"]), provider)
        if provider is not None and result.classifier != "llm":
            fallbacks += 1
        cat_pairs.append((row["category"], result.category.value))
        urg_pairs.append((row["urgency"], result.urgency.value))
        latencies.append(result.latency_ms)
        predictions.append({"id": row["id"], "got": f"{result.category.value}/{result.urgency.value}", "classifier": result.classifier})
        if result.category.value != row["category"] or result.urgency.value != row["urgency"]:
            misses.append({
                "id": row["id"], "subject": row["subject"],
                "expected": f'{row["category"]}/{row["urgency"]}',
                "got": f"{result.category.value}/{result.urgency.value}",
            })
        print(f"\r{i}/{len(rows)}", end="", file=sys.stderr, flush=True) if sys.stderr.isatty() else None
        if provider is not None and sleep:
            time.sleep(sleep)
    print(file=sys.stderr)

    n = len(rows)
    cat_acc = sum(t == p for t, p in cat_pairs) / n
    urg_acc = sum(t == p for t, p in urg_pairs) / n
    both = sum(c[0] == c[1] and u[0] == u[1] for c, u in zip(cat_pairs, urg_pairs)) / n
    high_missed = sum(1 for t, p in urg_pairs if t == "high" and p != "high")
    cat_metrics = per_class(cat_pairs, CATS)
    return {
        "n": n,
        "category_accuracy": round(cat_acc, 4),
        "category_macro_f1": round(sum(m["f1"] for m in cat_metrics.values()) / len(CATS), 4),
        "urgency_accuracy": round(urg_acc, 4),
        "both_correct": round(both, 4),
        "high_urgency_missed": high_missed,
        "high_urgency_total": sum(1 for t, _ in urg_pairs if t == "high"),
        "llm_fallbacks": fallbacks,
        "median_latency_ms": sorted(latencies)[n // 2],
        "per_category": cat_metrics,
        "per_urgency": per_class(urg_pairs, URGS),
        "confusion": {t: {p: sum(1 for a, b in cat_pairs if a == t and b == p) for p in CATS} for t in CATS},
        "misses": misses,
        "predictions": predictions,
    }


def to_markdown(r: dict, title: str) -> str:
    lines = [
        f"# Evaluation: {title}", "",
        f"Run on {r['date']} against {r['n']} labelled synthetic emails (`data/{r['data_file']}`).", "",
        "| Metric | Result |", "|---|---|",
        f"| Category accuracy | {r['category_accuracy']:.1%} |",
        f"| Category macro-F1 | {r['category_macro_f1']:.3f} |",
        f"| Urgency accuracy | {r['urgency_accuracy']:.1%} |",
        f"| Category and urgency both correct | {r['both_correct']:.1%} |",
        f"| High-urgency emails missed | {r['high_urgency_missed']} of {r['high_urgency_total']} |",
        f"| Median latency | {r['median_latency_ms']} ms |",
    ]
    if r["classifier"] == "llm":
        lines.append(f"| LLM failures that fell back to baseline | {r['llm_fallbacks']} |")
    lines += ["", "## Per category", "", "| Category | Precision | Recall | F1 | Emails |", "|---|---|---|---|---|"]
    lines += [f"| {c} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} | {m['support']} |" for c, m in r["per_category"].items()]
    lines += ["", "## Confusion matrix (rows = true label, columns = predicted)", "",
              "| | " + " | ".join(CATS) + " |", "|---|" + "---|" * len(CATS)]
    lines += [f"| **{t}** | " + " | ".join(str(r["confusion"][t][p]) for p in CATS) + " |" for t in CATS]
    lines += ["", f"## Misses ({len(r['misses'])})", ""]
    if r["misses"]:
        lines += ["| ID | Subject | Expected | Got |", "|---|---|---|---|"]
        lines += [f"| {m['id']} | {m['subject']} | {m['expected']} | {m['got']} |" for m in r["misses"]]
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--classifier", choices=["baseline", "llm"], default="baseline")
    ap.add_argument("--data", default=str(ROOT / "data" / "emails.jsonl"))
    ap.add_argument("--sleep", type=float, default=2.2, help="seconds between LLM calls (free tiers allow ~30/min)")
    ap.add_argument("--limit", type=int, default=0, help="only evaluate the first N emails")
    args = ap.parse_args()

    rows = load(Path(args.data))
    if args.limit:
        rows = rows[: args.limit]

    provider, title = None, "keyword baseline"
    if args.classifier == "llm":
        s = config.load()
        if not s.api_key and s.provider != "ollama":
            sys.exit(f"No API key found for provider '{s.provider}'. Set it in your environment (see .env.example).")
        provider = OpenAICompatProvider(s.base_url, s.api_key, s.model, s.timeout_s)
        title = f"LLM ({s.provider}, {s.model})"
        # One test call first. Without it, a wrong key or model name would make every
        # email fall back to the keyword rules and the report would not be an LLM result.
        try:
            provider.complete("Reply with the JSON object {\"ok\": true}.", "ping")
        except LLMError as exc:
            sys.exit(f"The LLM is not reachable, so nothing was measured.\n  {explain(exc)}")

    report = evaluate(rows, provider, args.sleep)
    if provider is not None and report["llm_fallbacks"] > len(rows) // 2:
        sys.exit(f"{report['llm_fallbacks']} of {len(rows)} LLM calls failed, so this is not an LLM result. Nothing was written.")
    report.update({"classifier": args.classifier, "title": title, "date": date.today().isoformat(), "data_file": Path(args.data).name})
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    stem = Path(args.data).stem
    name = args.classifier if stem == "emails" else f"{args.classifier}_{stem.removeprefix('emails_')}"
    (out / f"{name}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / f"{name}.md").write_text(to_markdown(report, title), encoding="utf-8")

    print(f"{title}")
    print(f"  category accuracy : {report['category_accuracy']:.1%}")
    print(f"  urgency accuracy  : {report['urgency_accuracy']:.1%}")
    print(f"  both correct      : {report['both_correct']:.1%}")
    print(f"  high urgency missed: {report['high_urgency_missed']} of {report['high_urgency_total']}")
    print(f"  report: results/{name}.md")


if __name__ == "__main__":
    main()
