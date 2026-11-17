"""FastAPI backend."""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import approval as approval_manager, mindmap
from backend.orchestrator import ARTIFACTS, Orchestrator, recover_interrupted_stages
from agents.founder_agent import REQUIRED_FIELDS, normalize_state
from config import FRONTEND_DIR, OUTPUTS_DIR, STAGE_LABELS, STAGES, THEME_BY_CATEGORY
from memory import database
from services import decision_log, evidence_ledger, guardrails, trust
from tools.ollama_client import OllamaError, get_client

@asynccontextmanager
async def _lifespan(_app):
    _startup()  # recover interrupted stages and report model readiness, before serving requests
    yield


app = FastAPI(title="VentureOS", version="1.0.0", lifespan=_lifespan)
orchestrator = Orchestrator()
_analyze_cache: dict[str, dict] = {}


def _startup():
    import os as _os
    provider = _os.getenv("MODEL_PROVIDER", "ollama").lower().strip()
    recover_interrupted_stages()
    print("=" * 60)
    print("[VentureOS] Startup provider=" + provider)
    try:
        c = get_client()
        print("[VentureOS] Client: " + type(c).__name__)
        print("[VentureOS] Model: " + str(c.model))
        c.ensure_ready()
        print("[VentureOS] Ready")
    except OllamaError as e:
        print("[VentureOS] NOT READY")
        print(str(e))
    print("=" * 60)


class NewVenture(BaseModel):
    idea: str

class FounderView(BaseModel):
    venture_id: str
    message: str

class NewResearch(BaseModel):
    venture_id: str
    question: str

class ApproveRequest(BaseModel):
    venture_id: str
    approval_id: str
    choice: str = "continue"  # continue | repeat | pivot | stop — the founder's gate decision


class DemandTestRequest(BaseModel):
    signups: int


class DemandTargetRequest(BaseModel):
    signups: int
    days: int

class ThemePayload(BaseModel):
    theme: dict

class AskRequest(BaseModel):
    question: str
    history: list[dict] = []

class RenameRequest(BaseModel):
    name: str

class UpdateFieldRequest(BaseModel):
    field: str
    value: str


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.get("/api/health")
def health():
    c = get_client()
    try:
        c.ensure_ready()
        return {"ok": True, "model": c.model, "host": getattr(c, "host", "n/a")}
    except OllamaError as e:
        return JSONResponse(status_code=503, content={"ok": False, "error": str(e)})


@app.get("/api/config")
def config():
    return {"stages": STAGES, "stage_labels": STAGE_LABELS, "themes": THEME_BY_CATEGORY}


@app.get("/api/ventures")
def list_ventures():
    return database.list_ventures()


@app.post("/api/ventures")
def create_venture(body: NewVenture):
    if not body.idea.strip():
        raise HTTPException(400, "idea required")
    refusal = guardrails.check_idea(body.idea)
    if refusal:  # rule-based, before any model call: excluded products and must-never requests
        raise HTTPException(422, refusal["message"])
    v = database.create_venture(name="Untitled", idea=body.idea.strip())
    database.add_message(v["id"], "user", body.idea.strip())
    return v


@app.get("/api/ventures/{vid}")
def get_venture(vid: str):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    return {"venture": v, "stages": database.get_stages(vid),
            "messages": database.get_messages(vid),
            "evidence": evidence_ledger.list_for(vid),
            "evidence_summary": evidence_ledger.summary(vid),
            "approvals": approval_manager.list_pending(vid),
            # No paid API is ever called: local open-weight model + free web search.
            "cost": {"per_run_usd": 0.0, "basis": "Local open-weight model via Ollama and free web search — no paid APIs."}}


@app.post("/api/ventures/{vid}/rename")
def rename_venture(vid: str, body: RenameRequest):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    name = " ".join(body.name.split())[:80]
    if not name:
        raise HTTPException(400, "name required")
    brief = v.get("brief") or {}
    brief["name"] = name
    brief["name_locked"] = True  # a re-drafted brief must not overwrite the founder's choice
    database.update_venture(vid, name=name, brief=brief)
    return {"ok": True, "name": name}


# The prototype is AI-generated code: it may run JS but must not reach our API or submit anywhere.
_SANDBOX_CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                "img-src data: blob:; font-src data:; connect-src 'none'; form-action 'none'; "
                "frame-ancestors 'self'; base-uri 'none'")


@app.get("/api/ventures/{vid}/artifacts/{name}")
def get_artifact(vid: str, name: str):
    if not database.get_venture(vid) or name not in ARTIFACTS:
        raise HTTPException(404, "not found")
    path = (OUTPUTS_DIR / vid / ARTIFACTS[name]).resolve()
    if OUTPUTS_DIR.resolve() not in path.parents or not path.is_file():
        raise HTTPException(404, "This file hasn't been generated yet — run the stage first.")
    if path.suffix == ".md":
        return FileResponse(path, media_type="text/markdown; charset=utf-8", filename=path.name)
    headers = {"Content-Security-Policy": _SANDBOX_CSP} if name in ("prototype", "store-page") else {}
    return FileResponse(path, media_type="text/html; charset=utf-8", headers=headers)


@app.get("/api/ventures/{vid}/mindmap")
def get_mindmap(vid: str):
    try:
        return mindmap.build(vid)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/ventures/{vid}/mindmap/generate")
async def generate_mindmap(vid: str):
    """(Re)generate the 12-aspect business map. Only allowed once Discover has run."""
    if not database.get_venture(vid):
        raise HTTPException(404, "venture not found")
    if not mindmap.discover_done(vid):
        raise HTTPException(409, "Run the Discover stage first — the business map is built from its research.")
    try:
        await asyncio.to_thread(orchestrator.build_business_map, vid)
        _log_agent_call(vid, "business_map", "Regenerate business map")
        return mindmap.build(vid)
    except Exception as e:
        raise HTTPException(502, str(e))


@app.get("/api/ventures/{vid}/decisions")
def get_decisions(vid: str):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    return decision_log.list_for(vid)


def _collect_answers(vid):
    v = database.get_venture(vid)
    answers = dict(normalize_state(v.get("discovery"))["answers"])
    overrides = (v.get("brief") or {}).get("field_overrides") or {}
    answers.update({k: val for k, val in overrides.items() if val})
    return answers


@app.get("/api/ventures/{vid}/summary")
def get_summary(vid: str):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    answers = _collect_answers(vid)
    return {"idea": v["idea"], "answers": answers, "answered_fields": sorted(answers)}


@app.post("/api/ventures/{vid}/analyze-summary")
def analyze_summary(vid: str):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    answers = {k: val for k, val in _collect_answers(vid).items() if k in REQUIRED_FIELDS}
    if not answers:
        return {"raw": {}, "analyzed": {}}
    cache_key = vid + "|" + "|".join(f"{k}={val}" for k, val in sorted(answers.items()))
    if cache_key in _analyze_cache:
        return {"raw": answers, "analyzed": _analyze_cache[cache_key]}
    try:
        analyzed = orchestrator.founder.analyze_answers(answers)
    except Exception as e:
        raise HTTPException(502, str(e))
    _log_agent_call(vid, "founder_understanding", "Analyse interview answers", ", ".join(sorted(answers)))
    _analyze_cache[cache_key] = analyzed
    return {"raw": answers, "analyzed": analyzed}


@app.post("/api/ventures/{vid}/ask")
def ask(vid: str, body: AskRequest):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    if not body.question.strip():
        raise HTTPException(400, "question required")
    refusal = guardrails.check_request(body.question)
    if refusal:
        _log_refusal(vid, v, refusal)
        return {"answer": refusal["message"], "refused": True, "rule": refusal["rule"]}
    try:
        # No client-side history (e.g. a `?` question mid-interview) → use the stored conversation.
        history = body.history or database.get_messages(vid)
        answer = orchestrator.founder.answer_question(v, body.question.strip(), history)
    except Exception as e:
        raise HTTPException(502, str(e))
    _log_agent_call(vid, "founder_understanding", "Answer founder question (Ask AI)", body.question.strip()[:200])
    return {"answer": answer}


def _log_agent_call(vid, agent, action, detail=""):
    """Every model call made outside the six phases (interview, brief, Ask AI, research) is logged too."""
    v = database.get_venture(vid) or {}
    decision_log.log(vid, stage=v.get("current_stage") or "discover", agent=agent, action=action,
                     decision="DONE", rationale=str(detail)[:400])


def _log_refusal(vid, v, refusal):
    decision_log.log(vid, stage=v.get("current_stage") or "discover", agent="guardrails",
                     action=f"Refused request ({refusal['rule']})", decision="REFUSED",
                     rationale=refusal["message"], model="rule-based")


@app.post("/api/ventures/{vid}/update-field")
def update_field(vid: str, body: UpdateFieldRequest):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    field = body.field.strip()
    # Founder brief fields the founder can set or correct directly (the problem statement's brief:
    # skills, budget, available time, target market and values).
    if field not in ("budget", "skills", "education", "target_market", "available_time", "values"):
        raise HTTPException(400, f"invalid field: {field}")
    brief = v.get("brief") or {}
    overrides = brief.get("field_overrides") or {}
    overrides[field] = body.value.strip()
    brief["field_overrides"] = overrides
    database.update_venture(vid, brief=brief)
    _analyze_cache.pop(vid, None)
    return {"ok": True, "field": field, "value": body.value.strip(), "overrides": overrides}


@app.post("/api/founder/next-question")
def founder_next(body: FounderView):
    v = database.get_venture(body.venture_id)
    if not v:
        raise HTTPException(404, "venture not found")
    history = database.get_messages(body.venture_id)
    last = history[-1] if history else None
    # The idea itself is stored as the first user message on venture creation.
    is_initial = len(history) == 1 and last["role"] == "user" and last["content"] == body.message
    if not is_initial:
        database.add_message(body.venture_id, "user", body.message)
        history = database.get_messages(body.venture_id)
        refusal = guardrails.check_request(body.message)
        if refusal:
            _log_refusal(body.venture_id, v, refusal)
            database.add_message(body.venture_id, "assistant", refusal["message"])
            return {"question": refusal["message"], "ready_for_brief": False, "phase": "refused",
                    "refused": True, "rule": refusal["rule"]}
    try:
        res = orchestrator.founder.next_question(
            v["idea"], history, v.get("discovery"),
            new_message=None if is_initial else body.message)
    except Exception as e:
        raise HTTPException(502, str(e))
    _log_agent_call(body.venture_id, "founder_understanding", "Founder interview question",
                    res.get("question") or "Interview complete — ready for the brief")
    database.update_venture(body.venture_id, discovery=res.pop("state"))
    if res["question"]:
        database.add_message(body.venture_id, "assistant", res["question"])
    return res


def _save_brief(vid, v, brief):
    theme = THEME_BY_CATEGORY.get(brief.get("category", "general"), "indigo")
    old = v.get("brief") or {}
    for keep in ("field_overrides", "business_map", "name_locked"):
        if old.get(keep):
            brief[keep] = old[keep]
    if old.get("name_locked"):
        brief["name"] = v["name"]
    database.update_venture(vid, name=brief.get("name") or v["name"], brief=brief, theme=theme)
    return theme


@app.post("/api/founder/draft-brief")
def founder_brief(body: FounderView):
    v = database.get_venture(body.venture_id)
    if not v:
        raise HTTPException(404, "venture not found")
    history = database.get_messages(body.venture_id)
    try:
        brief = orchestrator.founder.draft_brief(v["idea"], history, _collect_answers(v["id"]))
    except Exception as e:
        raise HTTPException(502, str(e))
    _log_agent_call(body.venture_id, "founder_understanding", "Draft business brief", brief.get("name", ""))
    theme = _save_brief(body.venture_id, v, brief)
    return {"brief": brief, "theme": theme}


@app.post("/api/ventures/{vid}/redraft-brief")
def redraft_brief(vid: str):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    history = database.get_messages(vid)
    try:
        brief = orchestrator.founder.draft_brief(v["idea"], history, _collect_answers(v["id"]))
    except Exception as e:
        raise HTTPException(502, str(e))
    _log_agent_call(vid, "founder_understanding", "Re-draft business brief", brief.get("name", ""))
    theme = _save_brief(vid, v, brief)
    return {"brief": brief, "theme": theme}


@app.post("/api/ventures/{vid}/theme")
def set_theme(vid: str, body: ThemePayload):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    brief = v.get("brief") or {}
    brief["theme"] = body.theme
    database.update_venture(vid, brief=brief)
    return {"ok": True, "theme": body.theme}


@app.post("/api/ventures/{vid}/run-stage/{stage}")
async def run_stage(vid: str, stage: str):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    try:
        return await asyncio.to_thread(orchestrator.run_stage, vid, stage)
    except Exception as e:
        raise HTTPException(502, str(e))


@app.post("/api/approve")
def approve(body: ApproveRequest):
    try:
        return orchestrator.resolve_gate(body.venture_id, body.approval_id, body.choice)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/reject")
def reject(body: ApproveRequest):
    try:
        return orchestrator.reject(body.venture_id, body.approval_id)
    except Exception as e:
        raise HTTPException(400, str(e))


class TryPrompt(BaseModel):
    prompt: str


@app.get("/api/trust/red-team")
def trust_red_team():
    """Attack our own guardrails with every trick prompt in evals/trick_prompts.json."""
    return trust.red_team()


@app.post("/api/trust/try")
def trust_try(body: TryPrompt):
    """Let anyone type a trick prompt and see whether (and why) it is refused — no model is called."""
    if not body.prompt.strip():
        raise HTTPException(400, "prompt required")
    return trust.classify(body.prompt[:2000])


@app.get("/api/ventures/{vid}/trust")
def venture_trust(vid: str):
    if not database.get_venture(vid):
        raise HTTPException(404, "venture not found")
    return trust.scorecard(vid)


@app.post("/api/ventures/{vid}/demand-target")
def demand_target(vid: str, body: DemandTargetRequest):
    """Pre-register the demand-test kill criterion; locked once real results exist."""
    if body.signups < 1 or body.days < 1:
        raise HTTPException(400, "target sign-ups and days must be at least 1")
    try:
        return orchestrator.set_demand_target(vid, body.signups, body.days)
    except PermissionError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/api/ventures/{vid}/demand-test")
def demand_test(vid: str, body: DemandTestRequest):
    """MOCKED landing page; the founder reports the REAL sign-up count and the gate scores it."""
    if body.signups < 0:
        raise HTTPException(400, "sign-ups can't be negative")
    try:
        return orchestrator.record_demand_test(vid, body.signups)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/api/ventures/{vid}/publish-store-page")
def publish_store_page(vid: str):
    """MOCKED publish — refused unless the founder approved the Launch gate; never posts anything."""
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    from services import store_page
    try:
        res = store_page.publish(vid)
    except approval_manager.ApprovalRequired:
        raise HTTPException(403, "Publishing needs your approval of the Launch gate first.")
    decision_log.log(vid, stage="launch", agent="store_page", action="Store page publish (MOCKED)",
                     decision="APPROVED", rationale=res["message"], approval_status="approved", model="rule-based")
    return res


@app.post("/api/ventures/{vid}/stop")
def stop(vid: str):
    orchestrator.stop(vid)
    return {"ok": True}


@app.post("/api/research")
async def research(body: NewResearch):
    v = database.get_venture(body.venture_id)
    if not v:
        raise HTTPException(404, "venture not found")
    refusal = guardrails.check_request(body.question)
    if refusal:
        _log_refusal(body.venture_id, v, refusal)
        raise HTTPException(422, refusal["message"])
    try:
        res = await asyncio.to_thread(orchestrator.research.run,
                                      {"venture": v, "question": body.question, "stage": v["current_stage"]})
    except Exception as e:
        raise HTTPException(502, str(e))
    _log_agent_call(body.venture_id, "research", f"Web research: {body.question[:80]}")
    return res


@app.middleware("http")
async def _no_stale_frontend(request, call_next):
    """Always revalidate the UI files, so a code change can't leave an old app.js running."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index():
    idx = FRONTEND_DIR / "index.html"
    if not idx.exists():
        raise HTTPException(500, "frontend/index.html missing")
    return FileResponse(idx)
