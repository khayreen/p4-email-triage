# Email & Complaint Triage

[![tests](https://github.com/khayreen/p4-email-triage/actions/workflows/ci.yml/badge.svg)](https://github.com/khayreen/p4-email-triage/actions/workflows/ci.yml)

An API that reads a bank customer's email, sorts it by **category** and **urgency**, and drafts a reply for a human agent to approve. Personal data is masked before anything reaches the language model, and nothing is ever sent without a person approving it.

Built as a portfolio project on the theme **build it, attack it, defend it**: the automation works, the system is attacked with its own test suite, and each defence is enforced by a test that fails if the defence is removed.

![Demo: reviewing a prompt-injection email, then approving a reply to a fraud report](docs/demo.gif)

*The review queue on the sample inbox. The first email is a prompt-injection attempt, flagged for review. Recorded without an LLM key, so the agent writes the reply; with a key, a draft is filled in for the agent to edit.*

## What it does

1. An email arrives through the API, a `.eml`/JSONL file, or a read-only Gmail connection.
2. IC numbers, cards, phones, account numbers, passports and email addresses are replaced with placeholders such as `[IC]`.
3. The masked email is screened for prompt-injection attempts.
4. An LLM classifies it and drafts a reply, answering in a strict JSON schema. Anything outside the schema is thrown away.
5. The result goes into a review queue. A human edits and approves the reply, or rejects it.

```mermaid
flowchart LR
    A[Email in<br/>API / file / Gmail] --> B[Mask PII]
    B --> C[Injection screen]
    C --> D[LLM classify + draft<br/>strict JSON schema]
    D -->|valid| E[Review rules]
    D -->|invalid or down| F[Keyword baseline]
    F --> E
    E --> G[(SQLite review queue)]
    G --> H[Human approves<br/>or rejects]
```

Categories: `fraud_security`, `complaint`, `account_services`, `card_services`, `financing`, `other`. Urgency: `high`, `medium`, `low`. Emails may be in English, Malay, or both.

## Results

Two sets of hand-written, labelled synthetic emails, about a fifth in Malay:

- **Main set**, 120 emails (`data/emails.jsonl`). The prompt's urgency rules were refined after looking at misses on this set.
- **Holdout set**, 42 emails (`data/emails_holdout.jsonl`). Written afterwards and never used to tune anything, so it is the fairer test.

### Main set (120 emails)

| Classifier | Category accuracy | Urgency accuracy | Both correct | High-urgency missed |
|---|---|---|---|---|
| Keyword baseline | 86.7% | 55.0% | 46.7% | 8 of 31 |
| LLM, first prompt | 96.7% | 76.7% | 75.0% | 5 of 30 |
| LLM, refined prompt | 97.5% | 90.0% | 88.3% | 1 of 31 |
| LLM, refined prompt + credential rule | 97.5% | 90.8% | 89.2% | 0 of 31 |

### Holdout set (42 emails)

| Classifier | Category accuracy | Urgency accuracy | Both correct | High-urgency missed |
|---|---|---|---|---|
| Keyword baseline | 66.7% | 57.1% | 40.5% | 4 of 13 |
| LLM, refined prompt | 95.2% | 97.6% | 95.2% | 0 of 13 |
| LLM, refined prompt + credential rule | 95.2% | 97.6% | 95.2% | 0 of 13 |

**The number to quote is the holdout: 95.2% of emails had both category and urgency right, and no high-urgency email was missed.** That is up from 40.5% and 4 of 13 missed for the keyword baseline on the same emails.

The LLM rows use Groq's `openai/gpt-oss-120b`. Reports with the confusion matrix and every miss are in [`results/`](results/).

```
python -m eval.run_eval --classifier baseline                                     # no API key needed
python -m eval.run_eval --classifier llm
python -m eval.run_eval --classifier llm --data data/emails_holdout.jsonl
python -m eval.rescore results/llm.json results/llm_holdout.json                  # adds the credential rule
```

The "+ credential rule" rows were not a second LLM run. The rule is deterministic and only ever raises urgency, so `eval/rescore.py` applies it to the saved predictions of the run above, which gives exactly what a fresh run with the same answers would score.

### What the first LLM run showed

The first prompt got the category right 116 times out of 120, but urgency only 92 times. The misses had a pattern:

- **18 routine requests rated "medium" instead of "low"** (a fee waiver, a limit increase, a rate enquiry). The prompt said "medium" was for "a request that needs action within days", which fits almost any request.
- **5 high-urgency emails rated "medium"**: a threat to go to Bank Negara, a letter of demand, a customer who lost their job, and two deadlines within the week. The prompt's "high" only named fraud, lost access and legal threats.
- **4 category misses**: two complaints filed under the product they were about, and two card instalment requests filed as financing.

The fix was to the wording of the rules, not the model: the prompt now spells out what makes an email high, medium or low, and that being unhappy with the bank is a complaint whatever product it mentions. Reviewing the misses also exposed one inconsistent label (L18, a signing deadline put at risk by a bank error, was "medium" while two near-identical cases were "high"). It was corrected, which is why the baseline row counts 31 high-urgency emails and the first LLM row, measured before the correction, counts 30.

### What the refined prompt changed

On the main set, urgency accuracy rose from 76.7% to 90.0% and high-urgency misses fell from 5 to 1. The 13 remaining urgency misses on that set now lean the other way:

- **9 rated too low.** Eight are routine requests the labels call "medium" (a 6-month statement, a phone number change, cashback not credited, a card activation, early settlement) that the model now calls "low". Being a little slow on a routine request costs little, so I stopped tuning the prompt here: the first prompt erred high and the second errs low, and another round would mostly move the error around.
- **1 serious miss: F05**, a customer who typed their online banking password into a phishing site, rated "medium". That one is an active compromise. Rather than edit the prompt again, a rule in code (`guard.credentials_disclosed`) now sets urgency to "high" whenever a customer says, in English or Malay, that they entered or gave away a password, OTP, TAC or PIN. The model cannot lower it, and a test feeds the pipeline a model answer of "low" to prove that. Across all 162 labelled emails the rule fires on two, F05 and holdout HF7, both labelled high, and HF7 was already right.
- **3 category confusions**: a general "how do I avoid scams" question filed as account services (holdout HF6 is the same pattern), and a frozen account and a late-payment charge read as complaints.

The holdout scored higher than the main set. With 42 emails that gap is mostly noise, so the fair reading is that the refined prompt held up on emails it was never tuned on, not that it does better on them. One holdout label is arguable: HL6, an instalment deducted twice, is labelled financing/medium and the model said complaint/high. It was left as written, because changing a holdout label after seeing the result would be tuning on it.

**Read these numbers with care:**

- The emails are synthetic, and the main set was written by the same person who wrote the keyword rules. The baseline's drop from 86.7% to 66.7% category accuracy on the holdout set shows how much that flattered it.
- The refined prompt was written after seeing the main-set misses, so its main-set score will be optimistic. The holdout score is the one to quote.
- Both sets are small. On 42 emails, one email is 2.4 points.
- "High-urgency missed" matters more than overall accuracy: a missed fraud report costs far more than a mislabelled newsletter.
- Each LLM row is a single run. The credential rule was written after seeing F05 on the main set; on the holdout it fired once on an email the model already had right, so the holdout neither confirms nor refutes it.

## LLM providers

Every supported provider speaks the OpenAI-compatible chat API, so switching provider is a one-line setting:

| `LLM_PROVIDER` | Key variable | Notes |
|---|---|---|
| `groq` (default) | `GROQ_API_KEY` | Free tier, no card |
| `gemini` | `GEMINI_API_KEY` | Free tier, no card |
| `openrouter` | `OPENROUTER_API_KEY` | Free models available |
| `ollama` | none | Runs on your own machine |
| `baseline` | none | Keyword rules only |

Free-tier model names change. If a call fails with "model not found", set `LLM_MODEL` to a current model from the provider's list.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/triage` | Classify one email and add it to the queue |
| `GET` | `/queue?status=pending` | List queue items |
| `GET` | `/queue/{id}` | One item |
| `POST` | `/queue/{id}/approve` | Approve the draft, or an edited reply |
| `POST` | `/queue/{id}/reject` | Reject with a reason |
| `GET` | `/stats` | Counts by status and category |
| `GET` | `/health` | Which classifier is active |

There is deliberately no "send" endpoint. Approval records the final reply; sending stays a human action.

## Built it, attacked it, defended it

### Attack 1: does a customer's IC number leak?

A canary IC number (`900101-14-5678`), a test card number, a phone number and an account number are planted in an email and traced through the system.

| Place | Before | After |
|---|---|---|
| Prompt sent to the LLM | Would contain the raw email | Placeholders only (`[IC]`, `[CARD]`) |
| Application logs | A careless `log.info(email.body)` would leak | Every log record is masked at creation, process-wide |
| Web server access log | An IC in a URL query string was written in clear | Masked (`/queue?q=[IC]`) |
| API response fields derived from the model | n/a | Masked again on the way out |
| Review database | Holds the original | Still holds the original, on purpose (see below) |

The access-log row was a real finding: the first version of the log masking broke the web server's access logger, which the unit tests missed and only showed up when the server was run for real. It is now covered by a regression test.

### Attack 2: prompt injection inside the email

Ten attack emails in `data/attacks.jsonl` try to hijack the model: "ignore all previous instructions", fake `</email><system>` tags, zero-width characters hiding the trigger words, a Malay-language variant, and attempts to make the reply contain a phishing link or ask for an OTP.

Defences, strongest first:

1. **No authority to abuse.** The model cannot send, refund, or change anything. The worst a successful injection can do is mislabel one email or write a bad draft.
2. **Closed output schema.** The answer must be one of six categories and three urgencies with no extra fields. `{"action": "refund"}` is discarded, not obeyed.
3. **Instructions and data kept apart.** The email is passed as delimited data in the user message; angle brackets inside it are neutralised so it cannot close the block.
4. **Reply checks.** A draft containing a link, a placeholder, or a request for a password/PIN/OTP/TAC is held for review.
5. **Heuristic screen.** Known injection phrasing forces the item to human review. All 10 attack emails are flagged, with 0 false alarms on the 120 clean emails.
6. **Human approval.** Every reply needs a person.

**What this does not prove:** the heuristic screen catches the attacks in this repo, not attacks in general. A novel phrasing will get past it. That is why it only adds review and the structural defences (1 to 3 and 6) do not depend on it. Whether a given LLM actually resists each attack still needs to be measured against the live model.

### Attack 3: stored XSS through the review page

Email content is attacker-controlled and gets displayed to staff. The review page writes it with `textContent` only and never uses `innerHTML`; a test fails if that changes.

## Security notes

- **PII masking:** MyKad (with date validation), payment cards (Luhn-checked), Malaysian mobile and landline numbers, passports, email addresses, and any remaining 9 to 17 digit number. Names and street addresses are **not** masked; that needs a named-entity model and is the main gap.
- **Where personal data rests:** only in the SQLite review database, because the agent needs the original to reply. Keep it on an encrypted disk. It is git-ignored.
- **Least privilege:** the Gmail connector requests `gmail.readonly` only. The service holds no credential that can send mail or move money.
- **Urgency floor:** a customer who says they gave away a password, OTP, TAC or PIN is always "high", whatever the model says.
- **Human in the loop:** fraud cases, high urgency, low confidence, suspected injection and any LLM failure are flagged; nothing is sent automatically in any case.
- **Logging:** every decision is logged with category, urgency, confidence and PII counts, never values.
- **Access control:** set `SERVICE_API_KEY` to require an `X-API-Key` header. Compared in constant time.
- **Failure mode:** if the LLM is down or returns invalid output, the email is still queued using keyword rules and flagged, so nothing is dropped.
- **Data:** every email in this repo is synthetic. "Bank Contoh" is fictional. No real customer or employer data was used.

## Limitations

- The model now tends to rate routine requests "low" when the labels say "medium" (9 of 120 on the main set).
- General scam-awareness questions are filed as account services rather than fraud and security (F16, HF6).
- The credential rule matches phrasings, so an unusual way of saying "I gave them my OTP" will not trigger it; the model's own rating still applies then.
- The Gmail connector's message parsing is unit-tested, but the OAuth flow has not been run against a live mailbox.
- SQLite and a single process are fine for a demo, not for production volume.
- The API key is a single shared secret, with no per-user accounts or audit of who approved what.

## What I learned

<!-- Khayreen: write this section yourself after running the project and the attacks.
     Three or four honest sentences beat a polished paragraph. Ideas:
     - What surprised you when you ran the LLM evaluation?
     - Which emails did the model get wrong, and why do you think so?
     - Which attack worried you most? -->

## Project layout

```
app/
  schemas.py      strict input and output contracts
  pii.py          masking, plus process-wide log masking
  guard.py        injection screen, reply checks, credential-disclosure floor
  classifier.py   the pipeline and the system prompt
  baseline.py     keyword classifier (comparison and fallback)
  llm.py          one client for all OpenAI-compatible providers
  store.py        SQLite review queue
  main.py         FastAPI routes;  asgi.py is the server entry point
  review.html     review page
  ingest/         .eml / JSONL / Gmail loaders
data/             120 + 42 labelled emails, 12 attack emails, a sample inbox
eval/run_eval.py  accuracy, per-class metrics, confusion matrix
eval/rescore.py   re-scores a saved run with the code rules
tests/            93 tests, including the attack tests
```

## License

MIT
