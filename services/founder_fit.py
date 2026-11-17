"""Founder Fit — should THIS founder build THIS venture, with THEIR budget, time, skills and values?

Deterministic (no model): every insight quotes the founder's own answers; every estimate is labelled
ASSUMPTION. The verdict is advice, not a gate — the founder decides.
"""
from __future__ import annotations
import re

MVP_HOURS = {"codes": 80, "no_code": 160}   # ASSUMPTION: hours to a first working web MVP
SKILLS = {
    "code": r"\b(code|coding|python|javascript|typescript|developer|engineer|programm\w*|software|full[- ]?stack|web dev)",
    "design": r"\b(design\w*|figma|ui|ux)\b",
    "marketing": r"\b(marketing|content|social media|seo|growth|copywriting|community)\b",
    "sales": r"\b(sales|selling|business development|negotiat\w*|b2b)\b",
}


def _money(text):
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(k)?\b", str(text or ""), re.I)
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    return value * 1000 if m.group(2) else value


def _hours_per_week(text):
    t = str(text or "").lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:h|hrs?|hours?)\s*(?:a|per|/|each)?\s*(?:week|wk)", t)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:h|hrs?|hours?)\s*(?:a|per|/|each)?\s*day", t)
    if m:
        return float(m.group(1)) * 5
    if re.search(r"full[- ]?time", t):
        return 40.0
    if re.search(r"part[- ]?time", t):
        return 15.0
    return None


def assess(venture: dict, answers: dict) -> dict:
    brief = venture.get("brief") or {}
    budget_txt = answers.get("budget") or brief.get("budget") or ""
    time_txt = answers.get("available_time") or ""
    skills_txt = " ".join(str(x) for x in ([answers.get("skills") or ""] + list(brief.get("founder_skills") or [])))
    values_txt = answers.get("values") or ""
    idea = " ".join(str(x) for x in (venture.get("idea"), brief.get("solution"), brief.get("concept")) if x)

    has = {k: bool(re.search(p, skills_txt, re.I)) for k, p in SKILLS.items()}
    budget = _money(budget_txt)
    hours = _hours_per_week(time_txt)
    software = bool(re.search(r"\b(app|web|software|platform|tool|saas|ai|bot|dashboard|api|website)\b", idea, re.I))
    insights, verdict, reasons = [], "build", []

    if hours:
        mvp_hours = MVP_HOURS["codes" if has["code"] else "no_code"]
        weeks = mvp_hours / hours
        insights.append(f"Time: you said \"{time_txt}\" → about {weeks:.0f} weeks to a first MVP "
                        f"(ASSUMPTION: ~{mvp_hours} hours {'because you code' if has['code'] else 'without coding skills, using no-code tools'}).")
        if weeks > 12:
            verdict = "narrow"
            reasons.append(f"~{weeks:.0f} weeks to an MVP at your pace is too slow to learn fast — cut scope to one feature")
    else:
        insights.append("Time: not stated — add your available hours per week to get a realistic MVP timeline.")
        reasons.append("available time unknown")

    if not skills_txt.strip():
        insights.append("Skills: not stated — add them so the MVP plan matches what you can build yourself.")
        reasons.append("skills unknown")
    elif software and not has["code"]:
        verdict = "partner" if verdict == "build" else verdict
        reasons.append("this is a software product and your skills don't mention coding — find a technical co-founder or start no-code")
        insights.append(f"Skills: you said \"{answers.get('skills')}\" — no coding skill listed for a software product.")
    elif has["code"]:
        insights.append(f"Skills: you said \"{answers.get('skills')}\" — you can build the MVP yourself; that is your edge.")
    if not has["marketing"] and not has["sales"]:
        insights.append("Gap: no marketing or sales skill listed — the Launch phase is where most solo founders stall; "
                        "budget time for 10 customer conversations a week.")

    if budget is not None:
        if budget < 100:
            insights.append(f"Budget: you said \"{budget_txt}\" — stay on free tiers (local model, free hosting); "
                            "no paid ads until the waitlist gate passes.")
        else:
            insights.append(f"Budget: you said \"{budget_txt}\" — keep at least half in reserve until real demand "
                            "passes the pre-registered kill criterion.")
    else:
        insights.append("Budget: not stated — the pricing and break-even numbers can't be checked against your runway.")

    if values_txt:
        if re.search(r"privacy|data", values_txt, re.I):
            insights.append(f"Values: you said \"{values_txt}\" — the privacy policy is only a STUBBED draft; "
                            "review it before collecting any user data.")
        elif re.search(r"honest|transparen|fair", values_txt, re.I):
            insights.append(f"Values: you said \"{values_txt}\" — matches our rules: no fake reviews, no urgency tricks, "
                            "every claim sourced or labelled ASSUMPTION.")
        else:
            insights.append(f"Values: you said \"{values_txt}\" — check each launch claim against this before publishing.")
    else:
        insights.append("Values: not stated — add them so launch copy can be checked against what you stand for.")

    if venture.get("gate") == "STOP":
        verdict = "stop"
        reasons.insert(0, "the Discover gate recommended STOP on the evidence")
    if not hours and verdict == "build":
        verdict = "unknown"

    label = {"build": "Build it yourself", "partner": "Partner up first", "narrow": "Narrow the MVP first",
             "stop": "Don't start yet", "unknown": "Not enough about you yet"}[verdict]
    return {"verdict": verdict, "label": label, "reasons": reasons, "insights": insights,
            "skills_detected": [k for k, v in has.items() if v],
            "note": "Advice from your own answers; estimates are ASSUMPTION. You decide."}
