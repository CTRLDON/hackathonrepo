"""Opportunity agent — Discover core step "Find opportunities".

Sharpens the founder's idea by generating a few alternative angles (different
segment, format or business model), then scores every option — the original
included — against the same criteria. Scores come from the model, but the
weighted total and the ranking are computed here in code, and the founder
chooses: the system never silently swaps the idea.
"""
from __future__ import annotations
from pathlib import Path

from agents.base import BaseAgent
from services import evidence_ledger, guardrails

# criterion -> (weight, what a 5 means)
CRITERIA = {
    "pain":        (0.30, "customers clearly feel this problem today (evidence of pain)"),
    "founder_fit": (0.25, "fits the founder's skills, budget and available time"),
    "reach":       (0.15, "the founder can reach the first customers cheaply"),
    "buildable":   (0.15, "a small digital MVP can ship within weeks"),
    "gap":         (0.15, "existing alternatives leave a clear gap"),
}


def weighted_score(scores: dict) -> float:
    total = 0.0
    for key, (weight, _) in CRITERIA.items():
        try:
            s = float(scores.get(key, 0))
        except (TypeError, ValueError):
            s = 0.0
        total += weight * max(0.0, min(5.0, s))
    return round(total, 2)


class OpportunityAgent(BaseAgent):
    name = "opportunity"
    description = "Generates alternative angles on the idea and scores them against the original."
    system_prompt = ("You are a pragmatic venture analyst. Suggest realistic DIGITAL product variations only "
                     "(no physical goods, no financial, health or legal advice). Score honestly; when evidence "
                     "is missing, say so and score conservatively.")

    def find(self, venture, out_file: Path | None = None):
        evidence = [e["claim"] for e in evidence_ledger.list_for(venture["id"], stage="discover")][:20]
        answers = (venture.get("discovery") or {}).get("answers", {})
        crit = {k: f"1-5, where 5 = {d}" for k, (_, d) in CRITERIA.items()}
        schema = ('{"options": [{"title": "string (short)", "description": "string (1 sentence)", '
                  '"is_original": "boolean", "scores": {' + ", ".join(f'"{k}": 1' for k in CRITERIA) + '}, '
                  '"reasons": "string (1-2 sentences; label anything not in the evidence as ASSUMPTION)"}]}')
        try:
            out = self._chat_json({
                "founder_idea": venture.get("idea"),
                "founder_brief": answers,
                "research_findings": evidence,
                "criteria": crit,
                "instruction": ("Return 4 options: the founder's ORIGINAL idea (is_original=true) plus 3 alternative "
                                "angles on the same problem (e.g. a narrower segment, a different format such as "
                                "templates/course/service, or a different business model). Score each criterion 1-5."),
            }, schema_hint=schema)
            options = [o for o in (out.get("options") or []) if isinstance(o, dict) and o.get("title")]
        except Exception:
            options = []

        kept = []
        for o in options[:6]:
            text = f"{o.get('title', '')}. {o.get('description', '')}"
            if guardrails.check_idea(text):  # never suggest an excluded product
                continue
            o["score"] = weighted_score(o.get("scores") or {})
            o["is_original"] = bool(o.get("is_original"))
            kept.append(o)
        if not any(o["is_original"] for o in kept):
            kept.append({"title": "Original idea", "description": venture.get("idea", ""), "is_original": True,
                         "scores": {}, "score": 0.0,
                         "reasons": "Not scored — the model returned no score for the original idea (ASSUMPTION gap)."})
        kept.sort(key=lambda o: o["score"], reverse=True)
        best = kept[0]
        original = next(o for o in kept if o["is_original"])

        evidence_ledger.add(venture["id"], type="assumption",
                            claim=f"Opportunity scoring: top option '{best['title']}' ({best['score']}/5); "
                                  f"original idea scored {original['score']}/5",
                            details="Model judgement — ASSUMPTION unless backed by Discover sources",
                            agent=self.name, stage="discover")
        if out_file:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(self._markdown(venture, kept), encoding="utf-8")
        return {"options": kept, "best": best, "original": original}

    @staticmethod
    def _markdown(venture, options):
        head = " | ".join(["Option", "Score /5"] + [k.replace("_", " ").title() for k in CRITERIA] + ["Why"])
        rows = [f"| {head} |", "|" + "---|" * (len(CRITERIA) + 3)]
        for o in options:
            s = o.get("scores") or {}
            title = o["title"] + (" (original)" if o["is_original"] else "")
            rows.append("| " + " | ".join([title, f"**{o['score']}**"] + [str(s.get(k, "–")) for k in CRITERIA]
                                          + [str(o.get("reasons", "")).replace("|", "/")]) + " |")
        weights = ", ".join(f"{k.replace('_', ' ')} {int(w * 100)}%" for k, (w, _) in CRITERIA.items())
        return "\n".join([
            f"# Opportunities — {venture.get('name') or 'Venture'}", "",
            f"_Founder idea:_ {venture.get('idea')}", "",
            "Each option is scored 1–5 per criterion by the model (**ASSUMPTION** — model judgement over the "
            "Discover research). The weighted total is computed in code "
            f"({weights}). **The founder chooses**; the system never switches the idea on its own.", "",
            *rows, ""])
