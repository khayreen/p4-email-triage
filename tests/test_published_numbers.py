"""The README's results tables must match the saved reports in results/."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.rescore import rescore

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _row(label: str, r: dict) -> str:
    return (f"| {label} | {r['category_accuracy']:.1%} | {r['urgency_accuracy']:.1%} | {r['both_correct']:.1%} "
            f"| {r['high_urgency_missed']} of {r['high_urgency_total']} |")


@pytest.mark.parametrize("report", ["llm.json", "llm_holdout.json"])
def test_published_llm_numbers_match_the_saved_runs(report):
    path = ROOT / "results" / report
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert _row("LLM, refined prompt", saved) in README
    assert _row("LLM, refined prompt + credential rule", rescore(path)) in README


@pytest.mark.parametrize("report", ["baseline.json", "baseline_holdout.json"])
def test_published_baseline_numbers_match_the_saved_runs(report):
    saved = json.loads((ROOT / "results" / report).read_text(encoding="utf-8"))
    assert _row("Keyword baseline", saved) in README
