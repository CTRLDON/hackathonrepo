# outputs/

Results from real pipeline runs (never written by hand). Regenerate with `python scripts/run_demo.py`;
the mocked sale-to-cash test log comes from `python scripts/run_payment_test.py`.

Naming: `phase<N>_step<M>_<short-name>.<ext>` for step results and `phase<N>_gate_<short-name>.<ext>`
for gate decisions. Files ending in `_weak_idea` come from a deliberately weak idea ("An AI that predicts
lottery numbers with 99% accuracy") and show the Discover gate recommending **STOP**.

| File | What it is | Run |
|---|---|---|
| `phase1_step1_discover_weak_idea.json` | Discover: four sourced research topics, five-dimension feasibility (labelled ASSUMPTION: model judgement over the sources), stage report | Current demo run, `qwen2.5-coder:7b` (same run as `decision_log.json`) |
| `phase1_gate_stop_weak_idea.json` | Discover gate: **STOP** (not feasible), rationale labelled ASSUMPTION, the 10 specific source pages used (bare homepages dropped) | Current demo run |
| `phase1_step2_trust_report_weak_idea.md` | Trust report computed from that run's records: 20 sourced claims, 1 `ASSUMPTION`, 0 unlabelled | Current demo run |
| `payment_test_log.md` | Sale to cash test run — **MOCKED** payments, delivery, refund and reconciliation | `scripts/run_payment_test.py` |

Market claims cite a source URL or are labelled `ASSUMPTION`. Later phases (Validate to Operate) write the same
kind of files under these names when `python scripts/run_demo.py` runs the full pipeline. Per-venture working folders
(`outputs/<venture-id>/`) are created at runtime and are not committed.
