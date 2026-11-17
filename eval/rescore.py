"""Re-score a saved LLM run with the code rules that sit after the model.

  python -m eval.rescore results/llm.json
  python -m eval.rescore results/llm_holdout.json

The LLM runs in results/ were measured before the credential-disclosure floor
(app/guard.py) existed. The floor is deterministic and only ever raises urgency,
so applying it to the saved predictions gives exactly what a fresh run with the
same model answers would score, without spending API calls. Predictions are
rebuilt from the report: an email not listed under misses was predicted as its label.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app import guard
from app.pii import mask

ROOT = Path(__file__).resolve().parent.parent


def rescore(report_path: Path) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (ROOT / "data" / report["data_file"]).read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != report["n"]:
        raise ValueError(f"{report['data_file']} has {len(rows)} emails but the report scored {report['n']}")
    got = {m["id"]: m["got"].split("/") for m in report["misses"]}

    cat_ok = urg_ok = both_ok = high_total = high_missed = 0
    raised: list[str] = []
    misses: list[str] = []
    for row in rows:
        category, urgency = got.get(row["id"], (row["category"], row["urgency"]))
        text = f"{mask(row['subject'])[0]}\n{mask(row['body'])[0]}"
        if urgency != "high" and guard.credentials_disclosed(text):
            urgency = "high"
            raised.append(row["id"])
        c, u = category == row["category"], urgency == row["urgency"]
        cat_ok += c
        urg_ok += u
        both_ok += c and u
        if not (c and u):
            misses.append(row["id"])
        if row["urgency"] == "high":
            high_total += 1
            high_missed += urgency != "high"
    n = len(rows)
    return {
        "n": n,
        "category_accuracy": round(cat_ok / n, 4),
        "urgency_accuracy": round(urg_ok / n, 4),
        "both_correct": round(both_ok / n, 4),
        "high_urgency_missed": high_missed,
        "high_urgency_total": high_total,
        "raised_by_rule": raised,
        "misses": misses,
    }


def main() -> None:
    for arg in sys.argv[1:] or [str(ROOT / "results" / "llm.json")]:
        r = rescore(Path(arg))
        print(f"{arg} with code rules")
        print(f"  category accuracy : {r['category_accuracy']:.1%}")
        print(f"  urgency accuracy  : {r['urgency_accuracy']:.1%}")
        print(f"  both correct      : {r['both_correct']:.1%}")
        print(f"  high urgency missed: {r['high_urgency_missed']} of {r['high_urgency_total']}")
        print(f"  raised by rule    : {', '.join(r['raised_by_rule']) or 'none'}")


if __name__ == "__main__":
    main()
