"""Export the SQLite decision log to decision_log.json in the hackathon schema.

Every entry has timestamp, agent, action, sources, model, cost and approved_by. Gate decisions also
carry `outcome` (go / repeat / pivot / stop). Rule-based steps (gates, guardrails, founder choices,
templates) have model null and no sources; research-backed actions list the URLs behind that phase.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from memory.database import connect  # noqa: E402
from services.sources import specific  # noqa: E402

OUTCOMES = {"GO", "REPEAT", "PIVOT", "STOP"}
NO_SOURCES = {"founder", "founder (scripted demo run)", "founder_understanding", "guardrails", "gate",
              "policies", "store_page", "testing"}


def _default_model():
    try:
        from tools.ollama_client import get_client
        return get_client().model
    except Exception:
        return os.getenv("OLLAMA_MODEL") or None


def export(path="decision_log.json"):
    with connect() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM decisions ORDER BY created_at ASC").fetchall()]
        evidence = [dict(r) for r in c.execute(
            "SELECT venture_id, stage, source FROM evidence WHERE source IS NOT NULL AND source != '' "
            "ORDER BY created_at ASC").fetchall()]
    model = _default_model()
    sources_by = {}
    for e in evidence:
        lst = sources_by.setdefault((e["venture_id"], e["stage"]), [])
        if e["source"] not in lst:
            lst.append(e["source"])
    entries = []
    for d in rows:
        rule_based = d.get("model") == "rule-based"
        entry = {
            "timestamp": d.get("created_at"),
            "agent": d.get("agent"),
            "action": d.get("action"),
            "sources": [] if (rule_based or d.get("agent") in NO_SOURCES)
            else specific(sources_by.get((d.get("venture_id"), d.get("stage")), []))[:10],
            "model": None if rule_based else (d.get("model") if d.get("model") not in (None, "", "unknown") else model),
            "cost": 0,
            "approved_by": "founder" if d.get("approval_status") == "approved" else None,
            "phase": d.get("stage"),
        }
        if d.get("decision") in OUTCOMES:
            entry["outcome"] = d["decision"].lower()
        entries.append(entry)
    Path(path).write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"[export] {len(entries)} entries -> {path}")
    return len(entries)


if __name__ == "__main__":
    export(str(ROOT / "decision_log.json"))
