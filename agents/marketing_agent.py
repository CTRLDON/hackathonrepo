from __future__ import annotations
from agents.base import BaseAgent
from services import evidence_ledger


class MarketingAgent(BaseAgent):
    name = "marketing"
    description = "Marketing copy with evidence-linked claims."
    system_prompt = ("You write honest marketing copy. Never invent "
                    "testimonials, customers, revenue, or guarantees.")

    def generate_launch_materials(self, venture, evidence):
        ev = [{"id": e["id"][:8], "type": e["type"], "claim": e["claim"],
               "source": e["source"]} for e in evidence[:20]]
        schema = (
            '{"tagline": "string", "one_liner": "string", '
            '"claims": [{"text": "string", "evidence_id": "string", '
            '"status": "supported|unsupported"}], "call_to_action": "string"}'
        )
        result = self._chat_json({
            "venture_idea": venture["idea"], "brief": venture.get("brief", {}),
            "evidence": ev,
            "instruction": "Cite evidence per claim OR mark unsupported.",
        }, schema_hint=schema)

        unsupported = []
        for c in result.get("claims", []):
            if c.get("status") == "unsupported" or not c.get("evidence_id"):
                c["status"] = "unsupported"
                unsupported.append(c.get("text", ""))
                evidence_ledger.add(venture["id"], type="assumption",
                                    claim=f"Marketing claim (UNSUPPORTED): {c.get('text','')}",
                                    agent=self.name, stage="launch")
            else:
                evidence_ledger.add(venture["id"], type="verified",
                                    claim=f"Marketing claim (verified): {c.get('text','')}",
                                    source=f"evidence:{c['evidence_id']}",
                                    agent=self.name, stage="launch")

        return {"tagline": result.get("tagline", ""),
                "one_liner": result.get("one_liner", ""),
                "claims": result.get("claims", []),
                "unsupported_claims": unsupported,
                "call_to_action": result.get("call_to_action", "")}

    def draft_launch_posts(self, venture, materials, out_file=None):
        """Launch-post DRAFTS (Launch core step). Never posted: the founder posts them after approval.
        Every draft passes the outgoing-claim guardrail; anything that fails is dropped, not softened."""
        from services import guardrails
        schema = ('{"posts": [{"channel": "linkedin|x|community", "audience": "string", "text": "string"}]}')
        try:
            out = self._chat_json({
                "venture_name": venture.get("name"), "venture_idea": venture.get("idea"),
                "tagline": materials.get("tagline"), "one_liner": materials.get("one_liner"),
                "call_to_action": materials.get("call_to_action"),
                "claims_backed_by_evidence": [c.get("text") for c in materials.get("claims", [])
                                              if c.get("status") != "unsupported"],
                "instruction": ("Write 3 launch post drafts in the FOUNDER's own voice: one LinkedIn post "
                                "(<= 120 words), one X post (<= 260 characters) and one community post for a relevant "
                                "forum or subreddit that asks for honest feedback. Use ONLY the evidence-backed claims. "
                                "No income promises, no fake numbers, users or reviews, no urgency or countdowns."),
            }, schema_hint=schema)
            posts = [p for p in (out.get("posts") or []) if isinstance(p, dict) and str(p.get("text", "")).strip()]
        except Exception:
            posts = []
        kept, blocked = [], []
        for p in posts[:5]:
            hit = guardrails.check_claim(p["text"])
            (blocked if hit else kept).append({**p, "blocked_reason": hit["message"] if hit else None})
        for p in kept:
            evidence_ledger.add(venture["id"], type="assumption",
                                claim=f"Launch post draft ({p.get('channel')}) — DRAFT, not posted",
                                details=p["text"][:400], agent=self.name, stage="launch")
        if out_file:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            md = [f"# Launch posts — {venture.get('name') or 'Venture'}", "",
                  "**DRAFTS — not posted.** VentureOS never posts for you. After you approve the Launch gate, "
                  "you publish these yourself, from your own accounts.", ""]
            for p in kept:
                md += [f"## {str(p.get('channel', 'post')).title()} — for {p.get('audience', 'your audience')}", "",
                       p["text"].strip(), ""]
            if blocked:
                md += ["## Blocked by guardrails (not usable)", ""]
                md += [f"- {p.get('channel')}: {p['blocked_reason']}" for p in blocked] + [""]
            if not kept:
                md += ["_No usable drafts were produced this run (ASSUMPTION gap) — rerun Launch._", ""]
            out_file.write_text("\n".join(md), encoding="utf-8")
        return {"posts": kept, "blocked": blocked}
