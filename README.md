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
| Founder intake | Clarifying questions, required fields, business brief drafting | Working |
| 1. Discover | Parallel web research on competitors, pain points, market size, barriers | Working |
| 1. Discover | Five-dimension feasibility scoring | Working |
| 1. Discover | Customer interviews (Mom Test) — founder answers via chat | Working |
| 1. Discover | Gate: GO / REPEAT / PIVOT / STOP verdict | Working |
| 2. Validate | Lean-experiment design (hypothesis, method, success, failure, cost) | Working |
| 2. Validate | Landing-page demand test with waitlist | MOCKED — no real page is deployed |
| 2. Validate | Gate: ≥ 2 experiments designed → GO | Working |
| 3. Build | MVP feature specification | Working |
| 3. Build | Application scaffold (writes files to `outputs/<venture_id>/mvp/`) | Working |
| 3. Build | Smoke test generation and execution | Working |
| 3. Build | Gate: ≥ 3 features AND smoke tests pass → GO | Working |
| 4. Commercial setup | Pricing strategy | Working |
| 4. Commercial setup | Unit economics (gross margin, contribution, break-even) | Working |
| 4. Commercial setup | Legal policy drafts (terms, privacy, refunds) | MOCKED — not generated |
| 4. Commercial setup | Gate: gross margin > 20% → GO | Working |
| 5. Launch | Marketing copy, tagline, claim-to-evidence mapping | Working |
| 5. Launch | Store-page publishing | MOCKED — not published |
| 5. Launch | Product delivery to buyers | MOCKED — no real delivery |
| 5. Launch | Payment processing | MOCKED — no real or sandbox payments, per rules |
| 5. Launch | Gate: no unsupported claims → GO | Working |
| 6. Operate & Learn | Metrics analysis | Working |
| 6. Operate & Learn | Comparable historical-case research | Working |
| 6. Operate & Learn | Persevere-or-pivot memo | Working |
| Cross-cutting | Founder approve/reject at every gate (enforced in code) | Working |
| Cross-cutting | `decision_log.json` recording every agent action | Working |
| Cross-cutting | Evidence ledger with source URLs and `ASSUMPTION` labels | Working |
| Cross-cutting | Progress mind-map UI | Working |

The demo run's outputs are committed in `outputs/` and follow the `phase<N>_step<M>_<name>` / `phase<N>_gate_<name>` convention. Every market claim in `outputs/` cites a source URL or is labelled `ASSUMPTION`. The same demo run is recorded in `decision_log.json` at the repository root.

## Architecture

The system is a single FastAPI process wrapping an `Orchestrator` that runs six sequential phases. Each phase drives specialised agents under `agents/`, accumulates checkpoints and evidence, then pauses at a gate. Gates are explicit records in an approvals table; the pipeline will not advance until the founder presses Approve in the UI, enforced by `backend/approval_manager.py`. Every action an agent takes is appended to the decision log with its sources, the model name, its cost, and the approver. The founder agent's clarification flow precedes the pipeline so that ideas start from a brief (skills, budget, education, target market, values) rather than a one-liner. Full diagrams and phase-by-phase detail are in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Models and free resources

**Default — local open-weight model via Ollama.** `MODEL_PROVIDER=ollama` (default) and `OLLAMA_MODEL=qwen3:8b` (or `llama3.2:3b`, `gpt-oss:20b`) in `.env`. Ollama runs on the host or as a service in `docker-compose.yml`; pull the model once with `ollama pull qwen3:8b`. No API key, no network beyond the local Ollama daemon, no cost.

**Optional — Gemini free tier.** `MODEL_PROVIDER=gemini` and `GEMINI_API_KEY=<key>` in `.env`, using `gemini-2.5-flash` on the free quota via `google-genai`. Optional; the full pipeline runs on the local model.

**Web research** uses the free `ddgs` library. **Everything else** is local Python. No paid service is required at any point.

## Cost per run

About **$0.00 per run** on the default local setup (roughly 40k tokens across a full six-phase run, all executed locally). The `cost` field is `0` for every entry in the committed `decision_log.json`. On the Gemini free tier, cost is also $0.00 within the free quota.

## What our system will NOT do

- Promise income, revenue, or success of any kind. A weak idea receives a STOP recommendation instead of an optimistic spin.
- Create fake reviews, testimonials, sign-ups, or urgency timers.
- Impersonate the founder, a customer, or another brand.
- Hold, move, or refund money; create accounts; store passwords or card numbers.
- Publish, send, spend, or sign anything without an explicit founder approve step, enforced in code.
- Advance past a gate without a recorded founder approval.
- Hide core features behind a paywall.

## How the project stays alive after the hackathon

**Maintainers.** The initial team commits to triaging and merging pull requests for at least six months after the event, and to keeping `docker compose up` working on Windows, macOS, and Linux.

**Roadmap** (also in `ARCHITECTURE.md#roadmap`). Pluggable model backends (OpenAI-compatible, Anthropic, local vLLM), real payment-provider adapters behind a new `payments.py` interface once a concrete provider is chosen, a richer `outputs/` schema, and a per-phase evaluation harness under `evals/`.

**Community.** Issues labelled `good-first-issue` and `phase-N` for new agent roles. The pipeline shape — six phases, gates, approval-before-action — is stable and documented in `ARCHITECTURE.md`; new agents drop in without touching the orchestrator.

**Funding.** MIT-licensed, no paid runtime dependencies by design, so the project can run on free tiers indefinitely. Future sustainability: open-source grants (Mozilla Technology Fund, Sloan Foundation), GitHub Sponsors, and consulting on open-source agent pipelines. No feature will be moved behind a paywall.