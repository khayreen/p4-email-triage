# Evaluation: LLM (groq, openai/gpt-oss-120b)

Run on 2026-11-17 against 120 labelled synthetic emails (`data/emails.jsonl`).

| Metric | Result |
|---|---|
| Category accuracy | 97.5% |
| Category macro-F1 | 0.975 |
| Urgency accuracy | 90.0% |
| Category and urgency both correct | 88.3% |
| High-urgency emails missed | 1 of 31 |
| Median latency | 1691 ms |
| LLM failures that fell back to baseline | 0 |

## Per category

| Category | Precision | Recall | F1 | Emails |
|---|---|---|---|---|
| fraud_security | 1.00 | 0.95 | 0.97 | 20 |
| complaint | 0.91 | 1.00 | 0.95 | 20 |
| account_services | 0.95 | 0.95 | 0.95 | 20 |
| card_services | 1.00 | 0.95 | 0.97 | 20 |
| financing | 1.00 | 1.00 | 1.00 | 20 |
| other | 1.00 | 1.00 | 1.00 | 20 |

## Confusion matrix (rows = true label, columns = predicted)

| | fraud_security | complaint | account_services | card_services | financing | other |
|---|---|---|---|---|---|---|
| **fraud_security** | 19 | 0 | 1 | 0 | 0 | 0 |
| **complaint** | 0 | 20 | 0 | 0 | 0 | 0 |
| **account_services** | 0 | 1 | 19 | 0 | 0 | 0 |
| **card_services** | 0 | 1 | 0 | 19 | 0 | 0 |
| **financing** | 0 | 0 | 0 | 0 | 20 | 0 |
| **other** | 0 | 0 | 0 | 0 | 0 | 20 |

## Misses (14)

| ID | Subject | Expected | Got |
|---|---|---|---|
| F05 | Clicked a link and entered my password | fraud_security/high | fraud_security/medium |
| F16 | How do I protect myself from scams | fraud_security/low | account_services/low |
| C03 | Aduan tentang layanan pegawai | complaint/medium | complaint/low |
| C12 | Marketing calls will not stop | complaint/medium | complaint/low |
| C13 | Long queue, only one counter open | complaint/low | complaint/medium |
| A01 | Request for 6 months bank statement | account_services/medium | account_services/low |
| A11 | Tukar nombor telefon berdaftar | account_services/medium | account_services/low |
| A13 | Account frozen without notice | account_services/high | complaint/high |
| A17 | Statement for business account | account_services/medium | account_services/low |
| K08 | Cashback not credited | card_services/medium | card_services/low |
| K14 | Turn on overseas and online usage | card_services/medium | card_services/low |
| K15 | Late payment charge on card | card_services/low | complaint/medium |
| L01 | Early settlement of personal financing | financing/medium | financing/low |
| L15 | Redraw from flexi home loan | financing/low | financing/medium |
