# Evaluation: LLM (groq, openai/gpt-oss-120b)

Run on 2026-11-17 against 42 labelled synthetic emails (`data/emails_holdout.jsonl`).

| Metric | Result |
|---|---|
| Category accuracy | 95.2% |
| Category macro-F1 | 0.952 |
| Urgency accuracy | 97.6% |
| Category and urgency both correct | 95.2% |
| High-urgency emails missed | 0 of 13 |
| Median latency | 1698 ms |
| LLM failures that fell back to baseline | 0 |

## Per category

| Category | Precision | Recall | F1 | Emails |
|---|---|---|---|---|
| fraud_security | 1.00 | 0.86 | 0.92 | 7 |
| complaint | 0.88 | 1.00 | 0.93 | 7 |
| account_services | 0.88 | 1.00 | 0.93 | 7 |
| card_services | 1.00 | 1.00 | 1.00 | 7 |
| financing | 1.00 | 0.86 | 0.92 | 7 |
| other | 1.00 | 1.00 | 1.00 | 7 |

## Confusion matrix (rows = true label, columns = predicted)

| | fraud_security | complaint | account_services | card_services | financing | other |
|---|---|---|---|---|---|---|
| **fraud_security** | 6 | 0 | 1 | 0 | 0 | 0 |
| **complaint** | 0 | 7 | 0 | 0 | 0 | 0 |
| **account_services** | 0 | 0 | 7 | 0 | 0 | 0 |
| **card_services** | 0 | 0 | 0 | 7 | 0 | 0 |
| **financing** | 0 | 1 | 0 | 0 | 6 | 0 |
| **other** | 0 | 0 | 0 | 0 | 0 | 7 |

## Misses (2)

| ID | Subject | Expected | Got |
|---|---|---|---|
| HF6 | Safe banking while travelling | fraud_security/low | account_services/low |
| HL6 | Instalment deducted twice this month | financing/medium | complaint/high |
