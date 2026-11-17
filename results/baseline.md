# Evaluation: keyword baseline

Run on 2026-11-17 against 120 labelled synthetic emails (`data/emails.jsonl`).

| Metric | Result |
|---|---|
| Category accuracy | 86.7% |
| Category macro-F1 | 0.860 |
| Urgency accuracy | 55.8% |
| Category and urgency both correct | 47.5% |
| High-urgency emails missed | 7 of 30 |
| Median latency | 0 ms |

## Per category

| Category | Precision | Recall | F1 | Emails |
|---|---|---|---|---|
| fraud_security | 0.92 | 0.55 | 0.69 | 20 |
| complaint | 0.94 | 0.80 | 0.86 | 20 |
| account_services | 0.74 | 0.85 | 0.79 | 20 |
| card_services | 0.87 | 1.00 | 0.93 | 20 |
| financing | 0.95 | 1.00 | 0.98 | 20 |
| other | 0.83 | 1.00 | 0.91 | 20 |

## Confusion matrix (rows = true label, columns = predicted)

| | fraud_security | complaint | account_services | card_services | financing | other |
|---|---|---|---|---|---|---|
| **fraud_security** | 11 | 0 | 5 | 3 | 1 | 0 |
| **complaint** | 0 | 16 | 1 | 0 | 0 | 3 |
| **account_services** | 1 | 1 | 17 | 0 | 0 | 1 |
| **card_services** | 0 | 0 | 0 | 20 | 0 | 0 |
| **financing** | 0 | 0 | 0 | 0 | 20 | 0 |
| **other** | 0 | 0 | 0 | 0 | 0 | 20 |

## Misses (63)

| ID | Subject | Expected | Got |
|---|---|---|---|
| F03 | Card charged in another country | fraud_security/high | card_services/medium |
| F04 | Phishing SMS pretending to be Bank Contoh | fraud_security/medium | fraud_security/high |
| F05 | Clicked a link and entered my password | fraud_security/high | account_services/high |
| F06 | Someone opened an account using my IC | fraud_security/high | account_services/high |
| F07 | Lost wallet with both cards inside | fraud_security/high | card_services/high |
| F09 | Akaun saya digodam | fraud_security/high | account_services/high |
| F10 | Is this email really from you? | fraud_security/medium | fraud_security/high |
| F13 | Fake Bank Contoh page on Facebook | fraud_security/medium | financing/medium |
| F14 | Duplicate debit that I never authorised | fraud_security/high | account_services/medium |
| F16 | How do I protect myself from scams | fraud_security/low | fraud_security/high |
| F17 | Kad saya hilang dan ada transaksi | fraud_security/high | card_services/high |
| F18 | Cheque I did not write was cleared | fraud_security/high | account_services/high |
| F19 | Caller asked for my TAC number | fraud_security/medium | fraud_security/high |
| C04 | Your app keeps crashing | complaint/medium | other/low |
| C08 | ATM out of service for two weeks | complaint/medium | other/low |
| C12 | Marketing calls will not stop | complaint/medium | other/low |
| C13 | Long queue, only one counter open | complaint/low | complaint/medium |
| C16 | Your chatbot is useless | complaint/low | complaint/medium |
| C17 | Unhappy with branch closure | complaint/low | complaint/medium |
| C18 | Privacy complaint - statement sent to wrong address | complaint/high | complaint/medium |
| C19 | Poor handling of my late father's account | complaint/medium | account_services/medium |
| A02 | Update my mailing address | account_services/low | account_services/medium |
| A04 | Cara buka akaun simpanan | account_services/low | other/low |
| A07 | Close my current account | account_services/low | account_services/medium |
| A08 | Dormant account reactivation | account_services/low | account_services/medium |
| A10 | Fixed deposit maturity question | account_services/low | account_services/medium |
| A11 | Tukar nombor telefon berdaftar | account_services/medium | fraud_security/high |
| A12 | Open a joint account | account_services/low | account_services/medium |
| A13 | Account frozen without notice | account_services/high | complaint/high |
| A14 | Name correction on account | account_services/low | account_services/medium |
| A16 | Add nominee to my account | account_services/low | account_services/medium |
| A18 | Foreign currency transfer rates | account_services/low | account_services/medium |
| A20 | Standing instruction set up | account_services/low | account_services/medium |
| K01 | Request to waive annual fee | card_services/low | card_services/medium |
| K02 | Credit limit increase | card_services/low | card_services/high |
| K06 | Redeem reward points | card_services/low | card_services/medium |
| K09 | Convert purchase to instalment plan | card_services/low | card_services/medium |
| K10 | Change card PIN | card_services/low | card_services/medium |
| K11 | Supplementary card for spouse | card_services/low | card_services/medium |
| K13 | Batalkan kad kredit | card_services/low | card_services/medium |
| K15 | Late payment charge on card | card_services/low | card_services/medium |
| K16 | Contactless limit | card_services/low | card_services/medium |
| K17 | Balance transfer offer | card_services/low | card_services/medium |
| K18 | Upgrade to platinum card | card_services/low | card_services/medium |
| K20 | Card statement e-delivery | card_services/low | card_services/medium |
| L02 | Home financing application status | financing/high | financing/medium |
| L03 | Mohon penjadualan semula pembiayaan | financing/high | financing/medium |
| L04 | Car loan interest rate | financing/low | financing/medium |
| L05 | Missed instalment this month | financing/medium | financing/high |
| L06 | ASB financing enquiry | financing/low | financing/medium |
| L08 | Letter of demand received | financing/high | financing/medium |
| L09 | Refinance my house | financing/low | financing/high |
| L11 | Personal loan eligibility | financing/low | financing/medium |
| L12 | Release of car ownership after full settlement | financing/high | financing/medium |
| L13 | Change instalment deduction date | financing/low | financing/high |
| L14 | SME business financing | financing/low | financing/medium |
| L15 | Redraw from flexi home loan | financing/low | financing/medium |
| L17 | Education loan for my daughter | financing/low | financing/medium |
| L19 | Partial prepayment | financing/low | financing/medium |
| L20 | Guarantor wants to withdraw | financing/low | financing/medium |
| O01 | Boost your website ranking today | other/low | other/high |
| O17 | Out of office | other/low | other/high |
| O20 | Nice new branch | other/low | other/high |
