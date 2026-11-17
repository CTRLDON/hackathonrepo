# outputs/

Results from real pipeline runs (never written by hand). Regenerate with `python scripts/run_demo.py`;
the mocked sale-to-cash test log comes from `python scripts/run_payment_test.py`.

Naming: `phase<N>_step<M>_<short-name>.<ext>` for step results and `phase<N>_gate_<short-name>.<ext>`
for gate decisions. Files ending in `_weak_idea` come from a deliberately weak idea (an "AI that predicts
lottery numbers with 99% accuracy") and show the Discover gate recommending **STOP**.

| File | What it is |
|---|---|
| `phase1_step1_feasibility_weak_idea.json` | Discover research + five-dimension feasibility for the weak idea |
| `phase1_gate_stop_weak_idea.json` | Discover gate decision for the weak idea: **STOP**, with sources |
| `phase2_step1_validation_plan.md` | Validate: assumptions checked against sources, experiments, Mom Test interview script |
| `phase3_step1_mvp_readme.md` | Build: README of a generated MVP |
| `payment_test_log.md` | Sale to cash test run — **MOCKED** payments, delivery, refund and reconciliation |

Market claims cite a source URL or are labelled `ASSUMPTION`. Per-venture working folders
(`outputs/<venture-id>/`) are created at runtime and are not committed.
