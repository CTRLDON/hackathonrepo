# outputs/

Results from real pipeline runs (never written by hand). Regenerate with `python scripts/run_demo.py`;
the mocked sale-to-cash test log comes from `python scripts/run_payment_test.py`.

Naming: `phase<N>_step<M>_<short-name>.<ext>` for step results and `phase<N>_gate_<short-name>.<ext>`
for gate decisions. Files ending in `_weak_idea` come from a deliberately weak idea ("An AI that predicts
lottery numbers with 99% accuracy") and show the Discover gate recommending **STOP**.

| File | What it is | Run |
|---|---|---|
| `phase1_step1_discover_weak_idea.json` | Discover: four sourced research topics, five-dimension feasibility, stage report | Current demo run, `qwen2.5-coder:7b` (same run as `decision_log.json`) |
| `phase1_gate_stop_weak_idea.json` | Discover gate: **STOP** (not feasible), with the 14 sources used | Current demo run |
| `phase1_step2_trust_report_weak_idea.md` | Trust report computed from that run's records: 20 sourced claims, 1 `ASSUMPTION`, 0 unlabelled | Current demo run |
| `phase2_step1_validation_plan.md` | Validate: assumptions checked against sources, experiments, Mom Test interview script | Earlier run of the pipeline |
| `phase3_step1_mvp_readme.md` | Build: README of a generated MVP | Earlier run of the pipeline |
| `payment_test_log.md` | Sale to cash test run — **MOCKED** payments, delivery, refund and reconciliation | `scripts/run_payment_test.py` |

Market claims cite a source URL or are labelled `ASSUMPTION`. Per-venture working folders
(`outputs/<venture-id>/`) are created at runtime and are not committed.
