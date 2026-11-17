"""End-to-end demo. Fails fast — hard timeout per stage."""
from __future__ import annotations
import json, os, shutil, signal, sys, time, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.orchestrator import Orchestrator
from memory import database
from scripts.export_decision_log import export
from services.sources import specific

OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

STAGE_TIMEOUT = int(os.getenv("DEMO_STAGE_TIMEOUT", "300"))
STAGES = ["discover", "validate", "build", "commercial", "launch", "operate"]
WEAK = "An AI that predicts lottery numbers with 99% accuracy."
# Digital products only — physical goods, finance/crypto and health/legal advice are excluded.
STRONG = ("A web app that turns a freelance designer's discovery call notes into a structured "
          "project brief and quote. Target market: freelance designers in Egypt. "
          "I can code in Python, have a $300 budget and 10 hours a week; I value honest pricing.")


class _Timeout(Exception):
    pass


def _alarm(_s, _f):
    raise _Timeout(f"stage exceeded {STAGE_TIMEOUT}s")


def say(msg):
    print(msg, flush=True)


def save(rel, data):
    p = OUT / rel
    p.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    say(f"  [out] {rel}")


def run_stage_timed(orch, vid, stage):
    say(f"  [{stage}] starting (timeout={STAGE_TIMEOUT}s)...")
    t0 = time.time()
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(STAGE_TIMEOUT)
    try:
        result = orch.run_stage(vid, stage)
        say(f"  [{stage}] finished in {time.time()-t0:.1f}s")
        return result
    except _Timeout:
        say(f"  [{stage}] TIMEOUT after {time.time()-t0:.1f}s")
        return {"_timeout": True, "_stage": stage}
    except Exception as e:
        say(f"  [{stage}] ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
        return {"_error": str(e), "_stage": stage}
    finally:
        signal.alarm(0)


def dump(stage, result, phase, suffix=""):
    """Write phase<N>_step1_<stage><suffix>.json and phase<N>_gate_<outcome><suffix>.json."""
    save(f"phase{phase}_step1_{stage}{suffix}.json", {
        "stage": stage,
        "labels": ("Feasibility scores, reasons and rationale are ASSUMPTION: the model's judgement over the "
                   "sources it cites. Research findings carry their own source URL or type=assumption."),
        "result": result})
    if result.get("_timeout") or result.get("_error"):
        gate = "TIMEOUT" if result.get("_timeout") else "ERROR"
        save(f"phase{phase}_gate_{gate.lower()}{suffix}.json", {
            "stage": stage, "gate": gate,
            "reason": result.get("_error") or f"stage exceeded {STAGE_TIMEOUT}s — likely slow model or network",
            "sources_used": [],
        })
        return gate
    feas = result.get("feasibility") or {}
    report = result.get("report") or {}
    gate = feas.get("gate_recommendation") or report.get("decision") or "N/A"
    save(f"phase{phase}_gate_{gate.lower()}{suffix}.json", {
        "stage": stage,
        "gate": gate,
        "decision_text": report.get("decision_text"),
        "classification": feas.get("classification"),
        "rationale": feas.get("rationale") or report.get("summary"),
        "rationale_label": "ASSUMPTION — the model's judgement over the sources below; no single source backs each sentence",
        "sources_used": specific(feas.get("sources_used") or []),
        "assumptions_labelled": "findings without a source URL are stored as type=assumption",
        "approved_by": None,
    })
    return gate


def approve(orch, vid, aid):
    try:
        # Scripted run: logged as the scripted founder, not as a live founder click.
        orch.resolve_gate(vid, aid, "continue", actor="founder (scripted demo run)")
        say(f"  [gate] approved {aid[:8]}...")
    except Exception as e:
        say(f"  [gate] approve failed: {e}")


def run_weak(orch):
    say("\n=== Weak idea (expecting STOP) ===")
    v = database.create_venture(name="Lottery", idea=WEAK)
    database.add_message(v["id"], "user", WEAK)
    result = run_stage_timed(orch, v["id"], "discover")
    gate = dump("discover", result, 1, "_weak_idea")
    say(f"  [gate] {gate}")


# Per-venture artifacts copied into outputs/ under phase/step names (text formats only).
ARTIFACT_COPIES = [
    ("validation/validation_plan.md", "phase2_step2_validation_plan.md"),
    ("mvp/index.html", "phase3_step2_prototype.html"),
    ("commercial/policies.md", "phase4_step2_policy_drafts.md"),
    ("launch/store_page.html", "phase5_step2_store_page.html"),
    ("final/venture_report.html", "phase6_step2_venture_report.html"),
    ("final/trust_report.md", "phase6_step3_trust_report.md"),
    ("discover/opportunities.md", "phase1_step2_opportunities.md"),
    ("mvp/USER_GUIDE.md", "phase3_step3_user_guide.md"),
    ("launch/launch_posts.md", "phase5_step3_launch_posts.md"),
    ("final/support_kit.md", "phase6_step4_support_kit.md"),
    ("final/persevere_or_pivot_memo.md", "phase6_step5_persevere_or_pivot_memo.md"),
]


def copy_artifacts(vid):
    for rel, name in ARTIFACT_COPIES:
        src = OUT / vid / rel
        if src.is_file():
            shutil.copyfile(src, OUT / name)
            say(f"  [out] {name}")


def run_strong(orch):
    say("\n=== Strong idea (full pipeline) ===")
    v = database.create_venture(name="BriefBuilder", idea=STRONG)
    database.add_message(v["id"], "user", STRONG)
    for i, stage in enumerate(STAGES, 1):
        result = run_stage_timed(orch, v["id"], stage)
        gate = dump(stage, result, i)
        if result.get("_timeout") or result.get("_error"):
            say(f"  [{stage}] bailing out — remaining stages skipped")
            break
        aid = result.get("approval_id")
        if aid:
            approve(orch, v["id"], aid)
    copy_artifacts(v["id"])


def main():
    say(f"[demo] provider from env, per-stage timeout={STAGE_TIMEOUT}s")
    orch = Orchestrator()
    say("[demo] Orchestrator ready, starting weak idea")
    try:
        run_weak(orch)
    except Exception:
        traceback.print_exc()
    try:
        run_strong(orch)
    except Exception:
        traceback.print_exc()
    say("\n=== Exporting decision log ===")
    try:
        export(str(ROOT / "decision_log.json"))
    except Exception:
        traceback.print_exc()
    say("\nDone. See outputs/ and decision_log.json")


if __name__ == "__main__":
    main()