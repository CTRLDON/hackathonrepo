"""Orchestrator — six gated stages. Every stage ends the same way:
decision -> plain-English summary -> persisted report -> founder approval."""
from __future__ import annotations
import json
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.business_map_agent import BusinessMapAgent
from agents.case_research_agent import CaseResearchAgent
from agents.commercial_agent import CommercialAgent
from agents.development_agent import DevelopmentAgent
from agents.feasibility_agent import FeasibilityAgent
from agents.financial_agent import FinancialAgent
from agents.founder_agent import FounderAgent
from agents.marketing_agent import MarketingAgent
from agents.operations_agent import OperationsAgent
from agents.research_agent import ResearchAgent
from agents.strategy_agent import StrategyAgent
from agents.testing_agent import TestingAgent
from agents.validation_agent import ValidationAgent
from backend import approval as approval_manager, gates
from backend.state_manager import StateManager
from config import OUTPUTS_DIR, STAGES
from memory import database
from memory.database import connect
from memory.schemas import utcnow
from services import decision_log, evidence_ledger, guardrails, policies, sources, stage_report, store_page, venture_report

# Downloadable outputs, by public name -> path inside outputs/<venture id>/
ARTIFACTS = {
    "prototype": "mvp/index.html",
    "validation-plan": "validation/validation_plan.md",
    "report": "final/venture_report.html",
    "policies": "commercial/policies.md",
    "store-page": "launch/store_page.html",
    "trust-report": "final/trust_report.md",
}


def _log_agent(vid, stage, agent, action, detail="", model=None):
    """One decision-log entry per agent action (gates and founder choices are logged separately)."""
    decision_log.log(vid, stage=stage, agent=agent, action=action, decision="DONE",
                     rationale=str(detail)[:400], model=model)


LEAN_CANVAS = [("Problem", "problem"), ("Customer segments", "customers"),
               ("Unique value proposition", "value_proposition"), ("Solution", "solution"),
               ("Channels", "channels"), ("Revenue streams", "revenue"), ("Cost structure", "costs"),
               ("Key metrics", None), ("Unfair advantage", "competition")]


def lean_canvas(v):
    """Lean Canvas blocks filled from the Discover business map; unknowns are labelled ASSUMPTION."""
    aspects = {a.get("key"): a for a in ((v.get("brief") or {}).get("business_map") or {}).get("aspects", [])}
    out = []
    for label, key in LEAN_CANVAS:
        a = aspects.get(key) if key else None
        if a and a.get("status") != "gap":
            out.append(f"{label}: {a.get('summary', '')}"
                       + (" (ASSUMPTION — not yet backed by evidence)" if a.get("status") == "partial" else ""))
        elif key is None:
            out.append(f"{label}: waitlist sign-ups vs. the pre-set target (see demand test below)")
        else:
            out.append(f"{label}: unknown — ASSUMPTION to test")
    return out


def artifact_url(vid, name):
    return f"/api/ventures/{vid}/artifacts/{name}"


def _clear_checkpoints(vid, stage):
    with connect() as c:
        c.execute("UPDATE stage_state SET notes_json='{}', updated_at=? WHERE venture_id=? AND stage=?",
                  (utcnow(), vid, stage))


def _checkpoint(vid, stage, message, extra=None):
    for attempt in range(5):
        try:
            with connect() as c:
                row = c.execute("SELECT notes_json FROM stage_state WHERE venture_id=? AND stage=?",
                                (vid, stage)).fetchone()
                notes = {}
                if row and row["notes_json"]:
                    try:
                        notes = json.loads(row["notes_json"]) or {}
                    except Exception:
                        notes = {}
                cps = notes.get("checkpoints", [])
                entry = {"time": utcnow(), "message": message}
                if extra is not None:
                    entry["extra"] = extra
                cps.append(entry)
                notes["checkpoints"] = cps
                c.execute("UPDATE stage_state SET notes_json=?, updated_at=? WHERE venture_id=? AND stage=?",
                          (json.dumps(notes), utcnow(), vid, stage))
            return
        except Exception as e:
            if "locked" in str(e).lower() and attempt < 4:
                _time.sleep(0.1 * (attempt + 1))
                continue
            raise


def recover_interrupted_stages():
    """On startup nothing can be running — unstick stages a crash/restart left 'in_progress'."""
    with connect() as c:
        c.execute("UPDATE stage_state SET status='awaiting_input', updated_at=? WHERE status='in_progress'",
                  (utcnow(),))


class Orchestrator:
    def __init__(self):
        self.founder = FounderAgent()
        self.research = ResearchAgent()
        self.feasibility = FeasibilityAgent()
        self.validation = ValidationAgent()
        self.strategy = StrategyAgent()
        self.development = DevelopmentAgent()
        self.testing = TestingAgent()
        self.commercial = CommercialAgent()
        self.financial = FinancialAgent()
        self.marketing = MarketingAgent()
        self.operations = OperationsAgent()
        self.case_research = CaseResearchAgent()
        self.business_map = BusinessMapAgent()

    # ── Shared ───────────────────────────────────────────────────────────
    def build_business_map(self, vid, feasibility=None):
        """Generate the 12-aspect business map and store it on the brief."""
        v = database.get_venture(vid)
        if not v:
            raise ValueError("unknown venture")
        bmap = self.business_map.generate(v, feasibility=feasibility)
        bmap["generated_at"] = utcnow()
        fresh = database.get_venture(vid)  # re-read so concurrent brief edits aren't clobbered
        brief = fresh.get("brief") or {}
        brief["business_map"] = bmap
        database.update_venture(vid, brief=brief)
        return bmap

    def _start(self, vid, stage, first_message):
        v = database.get_venture(vid)
        if not v:
            raise ValueError("unknown venture")
        _clear_checkpoints(vid, stage)
        StateManager.set_stage(vid, stage, "in_progress")
        _checkpoint(vid, stage, first_message)
        return v

    def _finish(self, vid, stage, *, gate, rationale, agent, action, facts, fallback_summary,
                highlights=None, sections=None, links=None, extra=None):
        """Decision + summary + report + approval — identical for every stage."""
        _checkpoint(vid, stage, "Writing the stage summary…")
        summary = stage_report.summarize(self.founder.client, stage, gate, facts, fallback_summary)
        report = stage_report.build(stage, gate, summary, highlights=highlights,
                                    sections=sections, links=links)
        stage_report.save(vid, stage, report)
        database.update_venture(vid, gate=gate, gate_rationale=summary)
        decision_log.log(vid, stage=stage, agent=agent, action=action, decision=gate,
                         rationale=summary[:800])
        status = "stopped" if gate == "STOP" else "awaiting_approval"
        StateManager.set_stage(vid, stage, status)
        _checkpoint(vid, stage, "Decision ready — awaiting your approval")
        approval_id = approval_manager.request(vid, action=f"{stage}_gate", payload={
            "recommendation": gate, "decision_text": report["decision_text"],
            "rationale": summary, "stage_label": report["stage_label"], **(extra or {})})
        return {"stage_status": status, "approval_id": approval_id, "report": report}

    # ── 1. Discover ──────────────────────────────────────────────────────
    def run_discover(self, vid):
        v = self._start(vid, "discover", "Starting 4 research topics in parallel…")
        idea = v["idea"][:180]
        questions = [
            f"Competitors and pricing for {idea}",
            f"Customer pain points for {idea}",
            f"Market size and growth for {idea}",
            f"Barriers and regulations for {idea}",
        ]
        results = {}

        def _one(idx, q):
            return idx, self.research.run({"venture": v, "stage": "discover", "question": q})

        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(_one, i, q): (i, q) for i, q in enumerate(questions)}
            for fut in as_completed(futures):
                i, q = futures[fut]
                try:
                    _, result = fut.result()
                    results[i] = result
                    _log_agent(vid, "discover", "research", f"Web research: {q[:80]}",
                               f"{len(result.get('sources', []))} sources, {len(result.get('findings', []))} findings")
                    _checkpoint(vid, "discover", f"Topic {i + 1}/4 complete — {len(result.get('sources', []))} sources")
                except Exception as e:
                    results[i] = {"sources": [], "findings": []}
                    _checkpoint(vid, "discover", f"Topic {i + 1}/4 failed — {str(e)[:80]}")

        research = [results.get(i, {"sources": [], "findings": []}) for i in range(len(questions))]
        total_sources = sum(len(r.get("sources", [])) for r in research)
        total_findings = sum(len(r.get("findings", [])) for r in research)
        _checkpoint(vid, "discover", f"Found {total_sources} sources and {total_findings} findings")

        _checkpoint(vid, "discover", "Assessing feasibility across 5 dimensions…")
        feas = self.feasibility.run({"venture": v, "stage": "discover"})
        gate = gates.discover_gate(feas)
        _checkpoint(vid, "discover", f"Verdict: {str(feas.get('classification', '')).title()}")

        _checkpoint(vid, "discover", "Building business map (12 core aspects)…")
        bmap = None
        try:
            bmap = self.build_business_map(vid, feasibility=feas)
            gaps = sum(1 for a in bmap["aspects"] if a["status"] == "gap")
            _checkpoint(vid, "discover", f"Business map ready — 12 aspects, {gaps} gaps")
            _log_agent(vid, "discover", "business_map", "Business map (12 aspects)", f"{gaps} gaps")
        except Exception as e:
            _checkpoint(vid, "discover", f"Business map failed — {str(e)[:80]}")

        dims = feas.get("dimensions") or {}
        out = self._finish(
            vid, "discover", gate=gate, rationale=feas.get("rationale", ""), agent="feasibility",
            action="Feasibility decision",
            facts={"classification": feas.get("classification"), "rationale": feas.get("rationale"),
                   "dimensions": dims, "risks": feas.get("risks"), "sources": total_sources},
            fallback_summary=feas.get("rationale") or f"Research found {total_findings} findings.",
            highlights=[("Verdict", str(feas.get("classification", "—")).title()),
                        ("Sources found", total_sources), ("Findings", total_findings)],
            sections=[
                ("Feasibility by dimension (ASSUMPTION — the model's judgement over the sources listed)", [f"{k.title()}: {str(d.get('score', '?')).title()} — {d.get('reason', '')}"
                                              for k, d in dims.items() if isinstance(d, dict)]),
                ("Business map — 12 core aspects", [f"{a['label']}: {a['summary']}"
                                                    for a in (bmap or {}).get("aspects", [])]),
                ("Key risks", feas.get("risks") or []),
                ("Recommended next steps", feas.get("next_steps") or []),
            ],
            links=[("Open the business mind map", "#mindmap")] if bmap else None,
            extra={"classification": feas.get("classification"),
                   "sources_used": sources.specific(feas.get("sources_used", []))})
        return {**out, "feasibility": feas}

    # ── 2. Validate ──────────────────────────────────────────────────────
    def run_validate(self, vid):
        v = self._start(vid, "validate", "Picking the riskiest assumptions to test…")
        res = self.validation.validate(v, OUTPUTS_DIR / vid / "validation",
                                       on_progress=lambda m: _checkpoint(vid, "validate", m))
        a = res["assessments"]
        n_sup = sum(x["verdict"] == "supported" for x in a)
        n_con = sum(x["verdict"] == "contradicted" for x in a)
        n_unv = len(a) - n_sup - n_con
        _checkpoint(vid, "validate", f"{n_sup} supported, {n_con} contradicted, {n_unv} unverified")
        gate = gates.validate_gate(a)
        icon = {"supported": "Supported", "contradicted": "Contradicted", "unverified": "Unverified"}
        return self._finish(
            vid, "validate", gate=gate, rationale="", agent="validation", action="Assumption validation",
            facts={"assessments": a, "experiments_planned": len(res["experiments"])},
            fallback_summary=(f"We tested {len(a)} key assumptions against web evidence: {n_sup} supported, "
                              f"{n_con} contradicted and {n_unv} still unverified. "
                              f"{len(res['experiments'])} cheap experiments are planned to close the gaps."),
            highlights=[("Assumptions tested", len(a)), ("Supported", n_sup), ("Contradicted", n_con),
                        ("Unverified", n_unv), ("Experiments planned", len(res["experiments"]))],
            sections=[
                ("Assumptions", [f"{icon[x['verdict']]} — {x['assumption']} ({x['reasoning']})" for x in a]),
                ("Experiments to run", [f"{e.get('name')}: {e.get('method', '')} Success = {e.get('success_metric', '')} "
                                        f"({e.get('cost', '?')}, {e.get('time', '?')})" for e in res["experiments"]]),
                ("Customer interview questions (Mom Test)", res["interview_questions"]),
                ("Lean Canvas (from the business map)", lean_canvas(v)),
                ("Landing-page demand test (MOCKED — no page is deployed)", [
                    f"Pre-set target: {gates.WAITLIST_TARGET['signups']} waitlist sign-ups in "
                    f"{gates.WAITLIST_TARGET['days']} days, fixed before the test.",
                    "Enter the REAL sign-up count on the Overview when the test ends; the gate "
                    "recommends go, repeat, pivot or stop from that number. Sign-ups are never generated."]),
            ],
            links=[("Download validation plan & interview script", artifact_url(vid, "validation-plan"))])

    # ── 3. Build ─────────────────────────────────────────────────────────
    def run_build(self, vid):
        v = self._start(vid, "build", "Designing the MVP specification…")
        evidence = evidence_ledger.list_for(vid)
        spec = self.strategy.generate_mvp_spec(v, evidence)
        features = (spec.get("features") or [])[:5]
        _checkpoint(vid, "build", f"Defined {len(features)} MVP features")
        _log_agent(vid, "build", "strategy", "MVP specification", ", ".join(str(f.get("name")) for f in features))

        out_dir = OUTPUTS_DIR / vid / "mvp"
        build = self.development.scaffold_mvp(v, spec, out_dir,
                                              on_progress=lambda m: _checkpoint(vid, "build", m))
        _checkpoint(vid, "build", "Prototype built" + (" (template fallback)" if build["source"] != "ai" else ""))
        _checkpoint(vid, "build", "Running automated checks on the prototype…")
        test = self.testing.generate_smoke_test(v, spec, out_dir)
        _checkpoint(vid, "build", f"Checks: {test['output']}")
        _log_agent(vid, "build", "testing", "Automated prototype checks", test["output"], model="rule-based")

        gate = gates.build_gate(test["passed"], len(features))
        return self._finish(
            vid, "build", gate=gate, rationale="", agent="development", action="MVP prototype build",
            facts={"features": [f.get("name") for f in features], "tests": test["output"],
                   "built_by": "AI" if build["source"] == "ai" else "template fallback"},
            fallback_summary=(f"Built a clickable prototype with {len(features)} MVP features. "
                              f"Automated checks: {test['output']}."),
            highlights=[("Features", len(features)), ("Checks", test["output"]),
                        ("Built by", "AI" if build["source"] == "ai" else "Template (AI generation failed)")],
            sections=[
                ("MVP features", [f"{f.get('name')}: {f.get('purpose', '')}" for f in features]),
                ("Automated checks", [f"{'Passed' if c['passed'] else 'Failed'} — {c['check']}"
                                      + (f" ({c['detail']})" if c["detail"] else "") for c in test["checks"]]),
                ("Out of scope for now", spec.get("out_of_scope") or []),
            ],
            links=[("Open the prototype", artifact_url(vid, "prototype"))])

    # ── 4. Commercial ────────────────────────────────────────────────────
    def run_commercial(self, vid):
        v = self._start(vid, "commercial", "Preparing pricing strategy…")
        evidence = evidence_ledger.list_for(vid)
        pricing = self.commercial.prepare_pricing(v, evidence)
        _checkpoint(vid, "commercial", f"Pricing model: {str(pricing.get('model', '?')).title()}")
        _log_agent(vid, "commercial", "commercial", "Pricing strategy",
                   f"{pricing.get('model')} at {pricing.get('price_per_unit')} per {pricing.get('unit')}")
        policies.write(v, pricing, OUTPUTS_DIR / vid / ARTIFACTS["policies"])
        _checkpoint(vid, "commercial", "Drafted terms, privacy and refund policies (STUBBED template)")
        _log_agent(vid, "commercial", "policies", "Policy drafts (STUBBED template)",
                   "Terms, privacy and refunds — not legal advice", model="rule-based")
        fresh = database.get_venture(vid)
        brief = fresh.get("brief") or {}
        brief["pricing"] = {k: pricing.get(k) for k in ("model", "price_per_unit", "unit", "currency")}
        database.update_venture(vid, brief=brief)
        _checkpoint(vid, "commercial", "Calculating unit economics…")
        eco = self.financial.model_unit_economics(v, pricing)
        margin = eco.get("gross_margin_pct", 0)
        gate = gates.commercial_gate(margin)
        cur = eco.get("currency") or ""
        return self._finish(
            vid, "commercial", gate=gate, rationale="", agent="financial", action="Pricing and unit economics",
            facts={"pricing": pricing, "economics": {k: eco.get(k) for k in (
                "price_per_unit", "variable_cost_per_unit", "fixed_costs_monthly", "gross_margin_pct",
                "break_even_units")}},
            fallback_summary=(f"Recommended a {pricing.get('model', '?')} model at {pricing.get('price_per_unit', '?')} "
                              f"per {pricing.get('unit', 'unit')}. Gross margin is {margin}%, breaking even at "
                              f"{eco.get('break_even_units') or 'N/A'} units per month."),
            highlights=[("Pricing model", str(pricing.get("model", "—")).title()),
                        ("Price", f"{pricing.get('price_per_unit', '—')} per {pricing.get('unit', 'unit')}"),
                        ("Gross margin", f"{margin}%"),
                        ("Monthly fixed costs", f"{eco.get('fixed_costs_monthly')} {cur}".strip()),
                        ("Break-even", f"{eco.get('break_even_units') or 'N/A'} units / month"),
                        ("Confidence", str(pricing.get("confidence", "—")).title())],
            sections=[("Why this price", [pricing.get("rationale", "")]),
                      ("Competitor price anchors", pricing.get("competitor_anchors") or []),
                      ("Cost assumptions", eco.get("assumptions") or []),
                      ("Policies (STUBBED — draft template, not legal advice)",
                       ["Terms of service, privacy policy and refund policy drafts are ready for your review."]),
                      ("Payments", ["None of any kind — no payment provider, no sandbox."])],
            links=[("Open the policy drafts (STUBBED)", artifact_url(vid, "policies"))],
            extra={"classification": f"Gross margin {margin}%"})

    # ── 5. Launch ────────────────────────────────────────────────────────
    def run_launch(self, vid):
        v = self._start(vid, "launch", "Writing launch copy…")
        evidence = evidence_ledger.list_for(vid)
        m = self.marketing.generate_launch_materials(v, evidence)
        unsupported = list(m.get("unsupported_claims", []))
        # Output guardrail: income promises, fake urgency or fake social proof never go out, sourced or not.
        for c in m.get("claims", []):
            hit = guardrails.check_claim(c.get("text", ""))
            if hit:
                c["status"] = "unsupported"
                unsupported.append(f"{c.get('text', '')} — {hit['message']}")
        for fld in ("tagline", "one_liner", "call_to_action"):
            hit = guardrails.check_claim(m.get(fld) or "")
            if hit:
                unsupported.append(f"{fld.replace('_', ' ').capitalize()}: {m.get(fld)} — {hit['message']}")
                m[fld] = "[removed by guardrail]"
        if len(unsupported) > len(m.get("unsupported_claims", [])):
            _log_agent(vid, "launch", "guardrails", "Blocked launch copy",
                       f"{len(unsupported) - len(m.get('unsupported_claims', []))} item(s) blocked", model="rule-based")
        m["unsupported_claims"] = unsupported
        supported =[c.get("text", "") for c in m.get("claims", []) if c.get("status") != "unsupported"]
        _checkpoint(vid, "launch", f"{len(m.get('claims', []))} marketing claims, {len(unsupported)} need evidence")
        _log_agent(vid, "launch", "marketing", "Launch copy and claim check",
                   f"{len(m.get('claims', []))} claims, {len(unsupported)} unsupported")
        store_page.write(database.get_venture(vid), m, (v.get("brief") or {}).get("pricing"),
                         OUTPUTS_DIR / vid / ARTIFACTS["store-page"])
        _checkpoint(vid, "launch", "Store page drafted (MOCKED — not published)")
        _log_agent(vid, "launch", "store_page", "Store page draft (MOCKED, not published)", model="rule-based")
        gate = gates.launch_gate(unsupported)
        return self._finish(
            vid, "launch", gate=gate, rationale="", agent="marketing", action="Launch materials",
            facts={"tagline": m.get("tagline"), "claims": len(m.get("claims", [])), "unsupported": unsupported},
            fallback_summary=(f"Prepared launch copy with {len(m.get('claims', []))} marketing claims; "
                              f"{len(unsupported)} still need evidence before you can publish them."),
            highlights=[("Tagline", m.get("tagline")), ("One-liner", m.get("one_liner")),
                        ("Call to action", m.get("call_to_action"))],
            sections=[("Claims backed by evidence", supported),
                      ("Claims that need evidence first", unsupported),
                      ("Store and delivery (MOCKED)", [
                          "Store page drafted locally and never published; publishing needs your Launch approval.",
                          "Payment → automatic delivery → refunds → reconciliation run as a MOCKED flow "
                          "(see outputs/payment_test_log.md). No money moves."])],
            links=[("Preview the store page (MOCKED)", artifact_url(vid, "store-page"))],
            extra={"unsupported_claims": unsupported})

    # ── 6. Operate (final) ───────────────────────────────────────────────
    def run_operate(self, vid):
        v = self._start(vid, "operate", "Pulling together everything learned so far…")
        context = {s: {k: r.get(k) for k in ("decision_text", "summary", "highlights")}
                   for s in STAGES if (r := stage_report.get(vid, s))}
        _checkpoint(vid, "operate", "Building the 90-day operating plan…")
        plan = self.operations.operating_plan(v, context)
        kpis, roadmap = plan.get("kpis") or [], plan.get("roadmap") or {}
        _checkpoint(vid, "operate", f"{len(kpis)} KPIs and a 30/60/90-day roadmap ready")

        cases = []
        risks = plan.get("risks") or []
        if risks:
            try:
                _checkpoint(vid, "operate", "Looking for comparable real-world cases…")
                cases = self.case_research.find_similar_cases(v, str(risks[0].get("risk", ""))[:100]).get("cases", [])
                _log_agent(vid, "operate", "case_research", "Comparable cases", f"{len(cases)} cases")
            except Exception:
                cases = []
        gate = gates.operate_gate()
        out = self._finish(
            vid, "operate", gate=gate, rationale="", agent="operations", action="Operating plan",
            facts={"kpis": kpis, "first_action": plan.get("first_action_tomorrow")},
            fallback_summary=(f"Your 90-day operating plan is ready with {len(kpis)} KPIs and a phased roadmap. "
                              f"The full venture report compiles every stage into one document."),
            highlights=[("First action tomorrow", plan.get("first_action_tomorrow")), ("KPIs", len(kpis))],
            sections=[
                ("KPIs (90-day targets)", [f"{k.get('metric')}: {k.get('target_90_days')} — {k.get('how_to_measure', '')}"
                                           for k in kpis]),
                ("Days 0–30", roadmap.get("days_0_30") or []),
                ("Days 31–60", roadmap.get("days_31_60") or []),
                ("Days 61–90", roadmap.get("days_61_90") or []),
                ("Risks & mitigations", [f"{r.get('risk')} → {r.get('mitigation')}" for r in risks]),
                ("Weekly operating rhythm", plan.get("weekly_rhythm") or []),
                ("Comparable cases", [f"{c.get('company')}: {c.get('outcome')}" for c in cases]),
            ],
            links=[("Open the full venture report", artifact_url(vid, "report")),
                   ("Open the trust report", artifact_url(vid, "trust-report")),
                   ("Open the prototype", artifact_url(vid, "prototype"))])
        # Report is compiled after this stage's own report is saved, so it's included.
        venture_report.write(database.get_venture(vid), OUTPUTS_DIR / vid / ARTIFACTS["report"])
        from services import trust
        trust.write_report(vid, OUTPUTS_DIR / vid / ARTIFACTS["trust-report"], v.get("name", ""))
        return out

    # ── Control ──────────────────────────────────────────────────────────
    def run_stage(self, vid, stage):
        if stage not in STAGES:
            raise ValueError(f"unknown stage: {stage}")
        v = database.get_venture(vid)
        if not v:
            raise ValueError("unknown venture")
        if v["current_stage"] != stage:
            return {"status": "wrong_stage",
                    "message": f"You are on '{v['current_stage']}', not '{stage}'."}
        stages = database.get_stages(vid)
        current_status = stages[stage]["status"]
        if current_status in ("in_progress", "awaiting_approval", "completed") or approval_manager.list_pending(vid):
            return {"status": "already_ran",
                    "message": "A founder decision is pending for this stage — choose continue, repeat, pivot "
                               "or stop first. Nothing runs past a gate without your decision."}
        if current_status in ("awaiting_input", "stopped"):
            # Re-run after the founder chose repeat / pivot / stop or rejected: start clean, and log it.
            with database.connect() as c:
                c.execute("DELETE FROM evidence WHERE venture_id=? AND stage=?", (vid, stage))
            decision_log.log(vid, stage=stage, agent="founder", action=f"Re-run {stage}",
                             decision="DONE", rationale="Founder started the phase again.", model="rule-based")
        dispatch = {"discover": self.run_discover, "validate": self.run_validate,
                    "build": self.run_build, "commercial": self.run_commercial,
                    "launch": self.run_launch, "operate": self.run_operate}
        try:
            return dispatch[stage](vid)
        except Exception as e:
            # Never leave a stage stuck "in_progress" — make it re-runnable.
            StateManager.set_stage(vid, stage, "awaiting_input")
            _checkpoint(vid, stage, f"Failed — {str(e)[:120]}. You can run the stage again.")
            raise

    @staticmethod
    def _pending_approval(vid, approval_id):
        if not any(a["id"] == approval_id for a in approval_manager.list_pending(vid)):
            raise ValueError("This decision was already resolved or doesn't belong to this venture.")

    def approve_and_advance(self, vid, approval_id):
        return self.resolve_gate(vid, approval_id, "continue")

    def resolve_gate(self, vid, approval_id, choice="continue", actor="founder"):
        """The founder decides what a gate actually does: continue, repeat, pivot back or stop.

        The gate's recommendation is advice; continuing against a REPEAT/PIVOT/STOP recommendation is
        an explicit, logged founder override. Every choice is recorded with approved_by = founder."""
        if choice not in gates.CHOICES:
            raise ValueError(f"unknown choice: {choice}")
        v = database.get_venture(vid)
        if not v:
            raise ValueError("unknown venture")
        self._pending_approval(vid, approval_id)
        rec = next((a["payload"].get("recommendation") for a in approval_manager.list_pending(vid)
                    if a["id"] == approval_id), None)
        stage = v["current_stage"]
        approval_manager.resolve(approval_id, "approved")
        follows = gates.CHOICES[choice] == rec
        label = {"continue": "continue to the next phase", "repeat": "repeat this phase",
                 "pivot": "pivot back", "stop": "stop the venture"}[choice]
        rationale = (f"Founder chose to {label}" + (" (as recommended)." if follows else
                     f" — overriding the {rec or 'gate'} recommendation."))
        result = {"choice": choice, "recommendation": rec, "override": not follows,
                  "advanced_to": stage, "finished": False}
        if choice == "continue":
            StateManager.set_stage(vid, stage, "completed")
            result["advanced_to"] = StateManager.advance_stage(vid)
            result["finished"] = stage == STAGES[-1]
        elif choice == "repeat":
            StateManager.set_stage(vid, stage, "awaiting_input")
        elif choice == "pivot":
            target = gates.PIVOT_TARGET[stage]
            for s in STAGES[STAGES.index(target) + 1:STAGES.index(stage) + 1]:
                StateManager.set_stage(vid, s, "not_started")
            StateManager.set_stage(vid, target, "awaiting_input")
            database.update_venture(vid, current_stage=target)
            result["advanced_to"] = target
        else:  # stop
            StateManager.set_stage(vid, stage, "stopped")
            database.update_venture(vid, gate="STOP")
        decision_log.log(vid, stage=stage, agent=actor,
                         action=f"Gate decision: {choice}" + (" (override)" if not follows else ""),
                         decision="APPROVED", rationale=rationale, approval_status="approved",
                         model="rule-based")
        return result

    def record_demand_test(self, vid, signups):
        """MOCKED landing page, REAL numbers: score founder-reported sign-ups against the pre-set target."""
        v = database.get_venture(vid)
        if not v:
            raise ValueError("unknown venture")
        res = gates.waitlist_gate(signups)
        brief = v.get("brief") or {}
        brief["demand_test"] = {**res, "recorded_at": utcnow(), "reported_by": "founder",
                                "landing_page": "MOCKED — no page deployed"}
        database.update_venture(vid, brief=brief)
        decision_log.log(vid, stage="validate", agent="gate", action="Waitlist demand gate",
                         decision=res["outcome"], rationale=res["rationale"], model="rule-based")
        return brief["demand_test"]

    def reject(self, vid, approval_id):
        self._pending_approval(vid, approval_id)
        approval_manager.resolve(approval_id, "rejected")
        v = database.get_venture(vid)
        if v:
            StateManager.set_stage(vid, v["current_stage"], "awaiting_input")
            decision_log.log(vid, stage=v["current_stage"], agent="founder",
                             action="Founder rejection", decision="REJECTED",
                             rationale="Founder rejected the decision; the stage can be run again.",
                             approval_status="rejected")
        return {"ok": True}

    def stop(self, vid):
        v = database.get_venture(vid)
        if v:
            StateManager.set_stage(vid, v["current_stage"], "stopped")
