"""Operations agent — turns everything learned into a 90-day operating plan."""
from __future__ import annotations
from agents.base import BaseAgent
from services import evidence_ledger


class OperationsAgent(BaseAgent):
    name = "operations"
    description = "Builds the 90-day operating plan: KPIs, roadmap, risks."
    system_prompt = ("You are a pragmatic startup operator. Every KPI needs a measurable target; every "
                     "roadmap item must be concrete and achievable by a small founding team. No generic advice.")

    def operating_plan(self, venture, context):
        schema = ('{"kpis": [{"metric": "string", "target_90_days": "string", "how_to_measure": "string"}], '
                  '"roadmap": {"days_0_30": ["string"], "days_31_60": ["string"], "days_61_90": ["string"]}, '
                  '"risks": [{"risk": "string", "mitigation": "string"}], '
                  '"weekly_rhythm": ["string"], "first_action_tomorrow": "string"}')
        result = self._chat_json({
            "venture_idea": venture.get("idea"), "venture_name": venture.get("name"),
            "everything_learned_so_far": context,
            "instruction": ("Create a 90-day operating plan to launch and run this venture: 4-6 KPIs with "
                            "targets, a 30/60/90-day roadmap (3-5 items each), top 3-4 risks with "
                            "mitigations, a weekly operating rhythm, and the single first action for tomorrow."),
        }, schema_hint=schema)
        for k in result.get("kpis") or []:
            evidence_ledger.add(venture["id"], type="assumption",
                                claim=f"KPI target: {k.get('metric', '')} → {k.get('target_90_days', '')}",
                                details=k.get("how_to_measure", ""), agent=self.name, stage="operate")
        return result

    def support_kit(self, venture, context, out_file=None):
        """Support core step: FAQ + reply templates. Drafts for the founder; nothing is sent."""
        schema = ('{"faq": [{"q": "string", "a": "string"}], '
                  '"reply_templates": [{"situation": "string", "reply": "string"}]}')
        try:
            out = self._chat_json({
                "venture_name": venture.get("name"), "venture_idea": venture.get("idea"),
                "what_we_know": context,
                "instruction": ("Write a support kit: 6 FAQ entries a first customer would really ask (pricing, "
                                "refunds, data/privacy, how it works, limits of the MVP) and 4 reply templates "
                                "(refund request, bug report, feature request, 'how do I…'). Be honest about what "
                                "the MVP does NOT do. Refunds follow the drafted refund policy and are processed by "
                                "the founder, never automatically. No promises of results."),
            }, schema_hint=schema)
        except Exception:
            out = {}
        faq = [f for f in (out.get("faq") or []) if isinstance(f, dict) and f.get("q")]
        replies = [r for r in (out.get("reply_templates") or []) if isinstance(r, dict) and r.get("reply")]
        if out_file:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            md = [f"# Support kit — {venture.get('name') or 'Venture'}", "",
                  "_Drafts for the founder. VentureOS never sends support replies or issues refunds itself._", "",
                  "## FAQ", ""]
            md += [f"**{f['q']}**  \n{f.get('a', '')}\n" for f in faq] or ["_No FAQ produced this run._", ""]
            md += ["## Reply templates", ""]
            md += [f"### {r.get('situation', 'Reply')}\n\n{r['reply']}\n" for r in replies] or ["_None this run._"]
            out_file.write_text("\n".join(md) + "\n", encoding="utf-8")
        return {"faq": faq, "reply_templates": replies}

    def pivot_memo(self, venture, context, plan, out_file=None):
        """Persevere-or-pivot memo (Operate core output). A recommendation; the founder decides."""
        schema = ('{"recommendation": "persevere|pivot|stop", "summary": "string (2-3 sentences)", '
                  '"evidence_for_persevering": ["string"], "evidence_against": ["string"], '
                  '"what_would_change_our_mind": ["string (measurable signal + threshold)"], '
                  '"if_pivot_then": "string"}')
        try:
            out = self._chat_json({
                "venture_name": venture.get("name"), "venture_idea": venture.get("idea"),
                "every_stage_so_far": context, "kpi_targets": plan.get("kpis"),
                "instruction": ("Write a persevere-or-pivot memo. Base it ONLY on the stage results given; most "
                                "evidence is still untested, so say so. Recommend 'stop' if the evidence is weak. "
                                "Give measurable signals (with thresholds) that would change the recommendation."),
            }, schema_hint=schema)
        except Exception:
            out = {}
        rec = out.get("recommendation") if out.get("recommendation") in ("persevere", "pivot", "stop") else "pivot"
        memo = {"recommendation": rec, "summary": str(out.get("summary") or ""),
                "for": [str(x) for x in out.get("evidence_for_persevering") or []],
                "against": [str(x) for x in out.get("evidence_against") or []],
                "signals": [str(x) for x in out.get("what_would_change_our_mind") or []],
                "if_pivot_then": str(out.get("if_pivot_then") or "")}
        evidence_ledger.add(venture["id"], type="assumption",
                            claim=f"Persevere-or-pivot memo: recommends {rec.upper()} (founder decides)",
                            details=memo["summary"][:400], agent=self.name, stage="operate")
        if out_file:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            md = [f"# Persevere-or-pivot memo — {venture.get('name') or 'Venture'}", "",
                  f"**Recommendation: {rec.upper()}** — a recommendation only; the founder decides.", "",
                  memo["summary"] or "_No summary produced (ASSUMPTION gap)._", "",
                  "## Evidence for persevering", *([f"- {x}" for x in memo["for"]] or ["- none yet"]), "",
                  "## Evidence against", *([f"- {x}" for x in memo["against"]] or ["- none recorded"]), "",
                  "## What would change our mind", *([f"- {x}" for x in memo["signals"]] or ["- not specified"]), ""]
            if memo["if_pivot_then"]:
                md += ["## If we pivot", memo["if_pivot_then"], ""]
            md += ["_Judgements here are ASSUMPTION unless the linked stage reports cite a source._"]
            out_file.write_text("\n".join(md) + "\n", encoding="utf-8")
        return memo
