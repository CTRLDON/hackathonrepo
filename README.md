# VentureOS

An open-source team of AI agents that takes a founder's idea through six gated phases — Discover, Validate, Build, Commercial setup, Launch, Operate & Learn — with sourced evidence, founder approval at every gate, and a real STOP recommendation when the evidence does not support moving on.

## Quickstart

```bash
docker compose up
```

Then open **http://localhost:8000** in a browser. The landing page asks for your idea; the founder agent asks a few clarifying questions, drafts a business brief, and unlocks the six-phase pipeline. The first run pulls the model weights and installs Python dependencies (a few minutes); later runs use cached layers and start in seconds.

See `.env.example` for the full list of settings. The default configuration uses a local Ollama model and requires no API key.

## What works and what is mocked

| Phase | Step | Status |
|---|---|---|
| Founder intake | Clarifying interview (one question at a time), required fields, business brief drafting | Working |
| Guardrails | Excluded products (physical goods; financial, investment or crypto; health or legal advice) and must-never requests refused before any model call (`services/guardrails.py`) | Working |
| 1. Discover | Parallel sourced web research on competitors, pain points, market size, barriers | Working |
| 1. Discover | Five-dimension feasibility verdict | Working |
| 1. Discover | 12-aspect business map and mind map | Working |
| 1. Discover | Gate: GO / REPEAT / PIVOT / STOP verdict | Working |
| 2. Validate | Riskiest assumptions checked against web evidence; Lean Canvas via the business map | Working |
| 2. Validate | Lean experiments and Mom Test customer-interview script (`validation_plan.md`) | Working |
| 2. Validate | Landing-page demand test with waitlist (no page deployed; founder enters real counts against a pre-set target) | MOCKED |
| 2. Validate | Gate: contradicted ≥ half → PIVOT; none contradicted and ≥ 1 supported → GO; else REPEAT | Working |
| 3. Build | MVP feature specification | Working |
| 3. Build | Clickable prototype written to `outputs/<venture_id>/mvp/` | Working |
| 3. Build | Automated prototype checks (HTML, features, no network calls, JS syntax) | Working |
| 3. Build | Gate: ≥ 3 features AND all checks pass → GO | Working |
| 4. Commercial setup | Pricing strategy | Working |
| 4. Commercial setup | Unit economics (gross margin, break-even) | Working |
| 4. Commercial setup | Legal policy drafts (terms, privacy, refunds), template only, not legal advice | STUBBED |
| 4. Commercial setup | Gate: gross margin > 20% → GO | Working |
| 5. Launch | Launch copy, tagline, claim-to-evidence mapping | Working |
| 5. Launch | Store-page publishing (never published) | MOCKED |
| 5. Launch | Sale to cash: `payments.py`, `delivery.py`, `refunds.py`, `reconcile.py` (no real or sandbox payments) | MOCKED |
| 5. Launch | Gate: no unsupported claims → GO | Working |
| 6. Operate & Learn | 90-day operating plan: KPIs, roadmap, risks | Working |
| 6. Operate & Learn | Comparable historical-case research | Working |
| 6. Operate & Learn | Persevere-or-pivot memo and full venture report | Working |
| Cross-cutting | Gate outcomes chosen by the founder: continue / repeat / pivot back / stop | Working |
| Cross-cutting | Founder approval enforced in code before advancing, publishing, sending or spending | Working |
| Cross-cutting | `decision_log.json` recording every agent action | Working |
| Cross-cutting | Evidence ledger with source URLs and `ASSUMPTION` labels | Working |
| Cross-cutting | Cost per run shown in the UI | Working |
| Cross-cutting | Trust Center: live red-team of the guardrails (`evals/trick_prompts.json`), try-a-trick-prompt box, honesty scorecard computed from the venture's records | Working |
| 5. Launch | Output guardrail: income promises, fake urgency and fake social proof in launch copy are blocked and fail the gate | Working |
| Cross-cutting | Agent prompts mirrored one file per agent in `prompts/` (`scripts/export_prompts.py`) | Working |
| Cross-cutting | Progress mind-map UI | Working |

The demo run's outputs are committed in `outputs/` and follow the `phase<N>_step<M>_<name>` / `phase<N>_gate_<name>` convention, including a STOP gate decision for a deliberately weak idea. The mocked sale-to-cash test run is in `outputs/payment_test_log.md`. Every market claim in `outputs/` cites a source URL or is labelled `ASSUMPTION`. The same demo run is recorded in `decision_log.json` at the repository root.

## Architecture

A single FastAPI process wraps an `Orchestrator` (`backend/orchestrator.py`) that runs six sequential phases, each driving specialised agents under `agents/` and recording sourced evidence. Every phase ends at a gate: thresholds live in `backend/gates.py`, and the founder resolves each gate in the UI (continue, repeat, pivot back or stop), enforced by `backend/approval.py`. A deterministic guardrail layer (`services/guardrails.py`) refuses excluded products and must-never requests before any model is called, and the Trust Center attacks it live with our own trick prompts. Every agent action is appended to the decision log with its sources, model, cost and approver. The mocked sale-to-cash flow (payment, delivery, refund, reconciliation) is described with diagrams in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Models and free resources

**Default — local open-weight model via Ollama.** `MODEL_PROVIDER=ollama` (default) and `OLLAMA_MODEL=qwen3:8b` (or `llama3.2:3b`, `gpt-oss:20b`) in `.env`. Ollama runs on the host or as a service in `docker-compose.yml`; pull the model once with `ollama pull qwen3:8b`. No API key, no network beyond the local Ollama daemon, no cost.

**Optional — Gemini free tier.** `MODEL_PROVIDER=gemini` and `GEMINI_API_KEY=<key>` in `.env`, using `gemini-2.5-flash` on the free quota via `google-genai`. Optional; the full pipeline runs on the local model.

**Web research** uses the free `ddgs` library. **Everything else** is local Python. No paid service is required at any point.

## Cost per run

About **$0.00 per run** on the default local setup (roughly 40k tokens across a full six-phase run, all executed locally). The `cost` field is `0` for every entry in the committed `decision_log.json`. On the Gemini free tier, cost is also $0.00 within the free quota.

## Demo video

Link coming soon (≤ 3 minutes).

## What our system will NOT do

- Promise income, revenue, or success of any kind. A weak idea receives a STOP recommendation instead of an optimistic spin.
- Create fake reviews, testimonials, sign-ups, or urgency timers.
- Impersonate the founder, a customer, or another brand.
- Hold, move, or refund money; create accounts; store passwords or card numbers.
- Publish, send, spend, or sign anything without an explicit founder approve step, enforced in code.
- Advance past a gate without a recorded founder approval.
- Hide core features behind a paywall.
- Work on excluded product types: physical goods; financial, investment or crypto products; health or legal advice products. These ideas are refused at intake.

## How the project stays alive after the hackathon

**Maintainers.** The initial team commits to triaging and merging pull requests for at least six months after the event, and to keeping `docker compose up` working on Windows, macOS, and Linux.

**Roadmap** (also in `ARCHITECTURE.md#roadmap`). More open-weight model backends (vLLM, llama.cpp), real payment-provider adapters behind the existing mocked `payments.py` / `delivery.py` / `refunds.py` / `reconcile.py` interfaces once a concrete provider is chosen (still founder-approved), a deployed landing page feeding the waitlist gate, and a per-phase evaluation harness under `evals/`.

**Community.** Issues labelled `good-first-issue` and `phase-N` for new agent roles. The pipeline shape — six phases, gates, approval-before-action — is stable and documented in `ARCHITECTURE.md`; new agents drop in without touching the orchestrator.

**Funding.** MIT-licensed, no paid runtime dependencies by design, so the project can run on free tiers indefinitely. Future sustainability: open-source grants (Mozilla Technology Fund, Sloan Foundation), GitHub Sponsors, and consulting on open-source agent pipelines. No feature will be moved behind a paywall.