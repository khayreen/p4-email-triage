# Email & Complaint Triage

[![tests](https://github.com/khayreen/p4-email-triage/actions/workflows/ci.yml/badge.svg)](https://github.com/khayreen/p4-email-triage/actions/workflows/ci.yml)

An API that reads a bank customer's email, sorts it by **category** and **urgency**, and drafts a reply for a human agent to approve. Personal data is masked before anything reaches the language model, and nothing is ever sent without a person approving it.

Built as a portfolio project on the theme **build it, attack it, defend it**: the automation works, the system is attacked with its own test suite, and each defence is enforced by a test that fails if the defence is removed.

![Review queue](docs/review-queue.png)

*The review queue running on the sample inbox in keyword-baseline mode (no LLM key). The second card is a prompt-injection email, flagged for review.*

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

Measured on 120 hand-written, labelled synthetic emails (`data/emails.jsonl`, 20 per category, about a fifth in Malay).

| Classifier | Category accuracy | Urgency accuracy | Both correct | High-urgency missed |
|---|---|---|---|---|
| Keyword baseline | 86.7% | 55.8% | 47.5% | 7 of 30 |
| LLM | *not measured yet* | | | |

The baseline row is reproducible with no API key: `python -m eval.run_eval --classifier baseline`. Full report with the confusion matrix and every miss: [`results/baseline.md`](results/baseline.md).

To fill in the LLM row, set an API key (see below) and run `python -m eval.run_eval --classifier llm`. It writes `results/llm.md`.

**Read these numbers with care:**

- The emails are synthetic and written by the same person who wrote the keyword rules, so the baseline is flattered. Real customer mail is messier.
- 120 emails is a small test set. A difference of a few points between two runs is noise.
- "High-urgency missed" matters more than overall accuracy: a missed fraud report costs far more than a mislabelled newsletter.

## Quick start

```bash
git clone https://github.com/khayreen/p4-email-triage.git
cd p4-email-triage
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

pytest -q                                            # 72 tests, no API key needed
python -m eval.run_eval --classifier baseline        # baseline accuracy
```

Run the service with an LLM:

```bash
cp .env.example .env          # then put your key in .env
uvicorn app.asgi:app --reload
python -m scripts.ingest --path data/sample_inbox.jsonl
```

Open <http://localhost:8000> for the review queue and <http://localhost:8000/docs> for the API docs.

### Choosing an LLM

Every supported provider speaks the OpenAI-compatible chat API, so switching is one line in `.env`:

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

```bash
curl -X POST localhost:8000/triage -H 'content-type: application/json' \
  -d '{"subject":"Lost card","body":"My wallet was stolen, please block my cards.","sender":"a@example.com"}'
```

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
- **Human in the loop:** fraud cases, high urgency, low confidence, suspected injection and any LLM failure are flagged; nothing is sent automatically in any case.
- **Logging:** every decision is logged with category, urgency, confidence and PII counts, never values.
- **Access control:** set `SERVICE_API_KEY` to require an `X-API-Key` header. Compared in constant time.
- **Failure mode:** if the LLM is down or returns invalid output, the email is still queued using keyword rules and flagged, so nothing is dropped.
- **Data:** every email in this repo is synthetic. "Bank Contoh" is fictional. No real customer or employer data was used.

## Limitations

- The LLM accuracy has not been measured yet (see Results).
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
  guard.py        injection screen and reply checks
  classifier.py   the pipeline and the system prompt
  baseline.py     keyword classifier (comparison and fallback)
  llm.py          one client for all OpenAI-compatible providers
  store.py        SQLite review queue
  main.py         FastAPI routes;  asgi.py is the server entry point
  review.html     review page
  ingest/         .eml / JSONL / Gmail loaders
data/             120 labelled emails, 12 attack emails, a sample inbox
eval/run_eval.py  accuracy, per-class metrics, confusion matrix
tests/            72 tests, including the attack tests
```

## License

MIT
