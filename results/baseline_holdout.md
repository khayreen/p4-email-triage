# Evaluation: keyword baseline

Run on 2026-11-17 against 42 labelled synthetic emails (`data/emails_holdout.jsonl`).

| Metric | Result |
|---|---|
| Category accuracy | 66.7% |
| Category macro-F1 | 0.618 |
| Urgency accuracy | 57.1% |
| Category and urgency both correct | 40.5% |
| High-urgency emails missed | 4 of 13 |
| Median latency | 0 ms |

## Per category

| Category | Precision | Recall | F1 | Emails |
|---|---|---|---|---|
| fraud_security | 0.80 | 0.57 | 0.67 | 7 |
| complaint | 0.33 | 0.14 | 0.20 | 7 |
| account_services | 0.50 | 0.29 | 0.36 | 7 |
| card_services | 0.78 | 1.00 | 0.88 | 7 |
| financing | 0.70 | 1.00 | 0.82 | 7 |
| other | 0.64 | 1.00 | 0.78 | 7 |

## Confusion matrix (rows = true label, columns = predicted)

| | fraud_security | complaint | account_services | card_services | financing | other |
|---|---|---|---|---|---|---|
| **fraud_security** | 4 | 1 | 1 | 1 | 0 | 0 |
| **complaint** | 0 | 1 | 1 | 0 | 2 | 3 |
| **account_services** | 1 | 1 | 2 | 1 | 1 | 1 |
| **card_services** | 0 | 0 | 0 | 7 | 0 | 0 |
| **financing** | 0 | 0 | 0 | 0 | 7 | 0 |
| **other** | 0 | 0 | 0 | 0 | 0 | 7 |

## Misses (25)

| ID | Subject | Expected | Got |
|---|---|---|---|
| HF2 | Caj tidak dikenali pada kad kredit | fraud_security/high | card_services/medium |
| HF3 | Call claiming to be from Bank Negara | fraud_security/medium | complaint/high |
| HF4 | Suspicious email asking me to update my details | fraud_security/medium | fraud_security/high |
| HF6 | Safe banking while travelling | fraud_security/low | account_services/medium |
| HC1 | Fourth visit and my documents were lost again | complaint/medium | financing/medium |
| HC3 | No parking at your branch | complaint/low | other/low |
| HC4 | Pegawai tidak menghubungi saya seperti dijanjikan | complaint/medium | other/low |
| HC5 | My lawyer will be writing to you | complaint/high | financing/high |
| HC6 | Your hold music | complaint/low | other/low |
| HC7 | Wrong overdraft fee and staff laughed at me | complaint/medium | account_services/medium |
| HA1 | Not receiving TAC, must pay supplier today | account_services/high | fraud_security/high |
| HA2 | Bank confirmation letter for embassy | account_services/medium | other/low |
| HA3 | Change my email address | account_services/low | account_services/medium |
| HA4 | Daftar DuitNow | account_services/low | card_services/medium |
| HA5 | Cheque deposited five days ago still not cleared | account_services/medium | complaint/medium |
| HA7 | Savings rate | account_services/low | financing/medium |
| HK2 | 0% instalment for a hospital bill | card_services/low | card_services/medium |
| HK4 | Cashback card for petrol | card_services/low | card_services/medium |
| HK7 | Change card statement date | card_services/low | card_services/medium |
| HL1 | Auction notice for my house | financing/high | financing/medium |
| HL2 | Lost my job, cannot pay car instalment | financing/high | financing/medium |
| HL3 | Personal financing for government staff | financing/low | financing/medium |
| HL4 | Disbursement to developer is late | financing/high | financing/medium |
| HL5 | Penyata baki pembiayaan | financing/low | financing/medium |
| HL7 | Top up my home loan | financing/low | financing/medium |
