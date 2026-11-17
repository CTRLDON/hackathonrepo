"""Guardrails — deterministic, rule-based checks that run BEFORE any model call.

Two kinds of checks:
- Excluded products (idea intake): physical goods; financial, investment or crypto products;
  health or legal advice products. These are outside the hackathon's scope for a digital product.
- Must-never requests (idea intake, founder chat, Ask AI, research): fake reviews / testimonials /
  sign-ups, manufactured urgency, impersonation, income or success promises, storing passwords or
  card numbers, and moving money.

No model is involved, so a trick prompt can't talk its way past these rules. Patterns favour
precision over recall: a false refusal blocks a founder, so only clear-cut phrasings are matched.
"""
from __future__ import annotations
import re

_F = re.IGNORECASE

EXCLUDED_PRODUCTS = [
    ("financial", "financial, investment or crypto products", [
        r"\b(crypto\w*|bitcoin|ethereum|altcoins?|nfts?|defi|forex|memecoins?)\b",
        r"\b(stock|share|options?|forex|crypto)[- ]?(picks?|tips|signals?|trading|predictions?)\b",
        r"\btrading (bot|signals?|algorithm)\b",
        r"\b(investment|investing|portfolio) (advice|advisor|app|platform|fund|recommendations?)\b",
        r"\brobo[- ]?advis\w*\b",
        r"\b(personal )?(loans?|lending|microloans?|credit scor\w*|insurance policies|insurance comparison)\b",
    ]),
    ("health", "health or medical advice products", [
        r"\b(medical|health) (advice|diagnos\w*|consultations?)\b",
        r"\b(diagnos(e|is|ing) (patients|diseases?|illness|symptoms)|symptom[- ]checker)\b",
        r"\b(prescri(be|bing|ptions?)|medication (advice|dosage)|dosage (advice|calculator))\b",
        r"\b(treatment plans?|therapy sessions?|telemedicine|online doctor)\b",
        r"\bmental health (advice|treatment|diagnos\w*|counsell?ing)\b",
    ]),
    ("legal", "legal advice products", [
        r"\b(legal advice|legal counsel|legal consultations?|ai lawyer|virtual lawyer|robot lawyer)\b",
        r"\b(immigration|visa) advice\b",
        r"\bdraft(s|ing)? (legal contracts|wills|legal documents)\b",
    ]),
    ("physical", "physical goods", [
        r"\bphysical (products?|goods|items)\b",
        r"\b(sell(ing|s)?|make|making|manufactur\w*|produc(e|ing)|ship(ping)?)\b[^.]{0,30}"
        r"\b(t-?shirts?|clothing|apparel|jewel(le)?ry|furniture|cosmetics|candles|handmade|merch(andise)?|"
        r"hardware|gadgets?|packaging|containers)\b",
        r"\b(subscription box(es)?|print[- ]on[- ]demand|3d[- ]print\w*|dropshipping)\b",
        r"\breusable (packaging|containers|cups|bottles)\b",
    ]),
]

MUST_NEVER = [
    ("fake_reviews", "write fake reviews, ratings or testimonials", [
        r"\b(fake|false|made[- ]up|invented|fabricat\w*|bogus)\b[^.]{0,30}\b(reviews?|ratings?|testimonials?|endorsements?)\b",
        r"\b(\d+|ten|twenty|fifty|hundred|some|several|a few)?\s*(five|5|four|4)[- ]star (reviews?|ratings?)\b",
        r"\b(write|generate|create|post|make|draft|invent)\b[^.]{0,25}\b(reviews|testimonials)\b(?![^.]{0,20}\b(section|page|widget|form|template)s?\b)",
    ]),
    ("fake_signups", "fake sign-ups, users or traction", [
        r"\b(fake|false|made[- ]up|make up|making up|fabricat\w*|inflat\w*|bogus)\b[^.]{0,30}\b(sign[- ]?ups?|waitlist|users|followers|downloads?|traction|customers|metrics|numbers|stats)\b",
    ]),
    ("false_urgency", "create fake urgency or countdown pressure", [
        r"\b(fake|false|artificial|manufactured)\b[^.]{0,20}\b(urgency|scarcity|deadlines?|countdowns?)\b",
        r"\bcountdown( timer)?\b[^.]{0,40}\b(urgency|pressure|buy now|limited offer|before it'?s gone)\b",
    ]),
    ("impersonation", "impersonate the founder, customers or another brand", [
        r"\b(impersonat\w*|pose as|posing as|pass (it|myself|ourselves) off as)\b",
        r"\bpretend(ing)? to be\b[^.]{0,40}\b(customers?|users?|clients?|the founder|a brand|another company|"
        r"apple|google|amazon|microsoft|a real person|someone else)\b",
    ]),
    ("income_promise", "promise income or guarantee success", [
        r"\b(guarantee[ds]?|promis(e|es|ed|ing))\b[^.]{0,40}\b(income|revenue|profits?|earnings|returns|success|"
        r"\$\s?\d[\d,]*k?|\d+k? (per|a) (month|week|day))\b",
        r"\bget[- ]rich[- ]quick\b",
    ]),
    ("credentials", "store passwords or card details", [
        r"\b(store|save|keep|collect|record|log)\b[^.]{0,25}\b(customers'?|users'?|their|my)?\s*"
        r"(passwords?|credit[- ]?card (numbers?|details)|card numbers?|cvv|bank (logins?|passwords?))\b",
    ]),
    ("move_money", "charge, transfer or refund money", [
        r"^\s*(please |now |go ahead and )?(charge|bill|refund|transfer|wire|send money|pay out)\b",
        r"\b(can|could|would|will) you (please )?(charge|bill|refund|transfer|wire|send|pay|process payments? for)\b"
        r"[^.?]{0,30}\b(money|funds|cards?|customers?|users?|payments?|\$\s?\d)",
    ]),
]

_COMPILED = {
    name: [(rule, label, [re.compile(p, _F) for p in pats]) for rule, label, pats in group]
    for name, group in (("excluded", EXCLUDED_PRODUCTS), ("never", MUST_NEVER))
}


def _first_match(text, group):
    for rule, label, pats in _COMPILED[group]:
        for p in pats:
            if p.search(text or ""):
                return rule, label
    return None


def check_request(text: str):
    """Must-never check for anything a founder asks the agents to do. None = allowed."""
    hit = _first_match(text, "never")
    if not hit:
        return None
    rule, label = hit
    return {"rule": rule, "kind": "must_never",
            "message": (f"I can't help with that: VentureOS will never {label}. "
                        "That protects your customers and keeps every claim honest. "
                        "I can help with an honest alternative instead — for example, a plan to collect real "
                        "feedback from real users, or copy that only states what the evidence supports.")}


def check_idea(text: str):
    """Excluded-product and must-never check for a new venture idea. None = allowed."""
    hit = _first_match(text, "excluded")
    if hit:
        rule, label = hit
        return {"rule": f"excluded_{rule}", "kind": "excluded_product",
                "message": (f"VentureOS only builds digital products, and {label} are excluded. "
                            "Try reframing the idea as a digital product — for example software, a web app, "
                            "templates, a course or a digital service — that doesn't give financial, "
                            "medical or legal advice.")}
    return check_request(text)


# Outgoing copy (launch posts, store page): language we never publish, whatever the evidence says.
CLAIM_RULES = [
    ("income_promise", r"\b(guarantee[ds]?|guaranteed|risk[- ]free|make money fast|passive income|get rich)\b"),
    ("false_urgency", r"\b(act now|hurry|limited time|only \d+ (left|spots|seats)|ends (tonight|today|soon)|last chance)\b"),
    ("fake_social_proof", r"\b(\d[\d,]*\+?|thousands of|millions of) (happy|satisfied|loyal) (customers|users|clients)\b"),
    ("fake_social_proof", r"\b(five|5)[- ]star (reviews?|rated)\b|\brated #?1\b|\b#1 (app|tool|platform)\b"),
]
_CLAIMS = [(rule, re.compile(p, _F)) for rule, p in CLAIM_RULES]


def check_claim(text: str):
    """Outgoing marketing claim check. None = publishable wording; else the rule it breaks."""
    for rule, p in _CLAIMS:
        if p.search(text or ""):
            return {"rule": rule, "message": f"Blocked by guardrail ({rule.replace('_', ' ')}): we never publish this."}
    return check_request(text)
