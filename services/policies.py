"""Policy drafts — STUBBED. Fixed templates (no model), filled with the venture's name and price.

Terms, privacy and refund drafts for a digital product. They are starting points for the founder to
review with a qualified professional: clearly labelled DRAFT and not legal advice.
"""
from __future__ import annotations
from pathlib import Path

STUBBED = True


def render(venture: dict, pricing: dict) -> str:
    name = (venture.get("brief") or {}).get("name") or venture.get("name") or "This product"
    price = pricing.get("price_per_unit", "the listed price")
    unit = pricing.get("unit", "unit")
    return f"""# Policy drafts — {name}

> **STUBBED — DRAFT TEMPLATE, NOT LEGAL ADVICE.** Generated from a fixed template, not written for your
> jurisdiction. Review with a qualified professional and approve before publishing anything.

## Terms of service (draft)

1. {name} is a digital product provided "as is". No income, results or success are promised.
2. Price: {price} per {unit}, shown before purchase. No payment is taken by this prototype.
3. Access is personal to the buyer and may be revoked if a refund is issued.
4. We may update these terms; material changes are announced before they apply.

## Privacy policy (draft)

1. We collect only what is needed to deliver the product: an account email and usage needed to run it.
2. We never store passwords in plain text or card numbers; payments would be handled by a payment provider.
3. We do not sell personal data. Buyers can ask for a copy or deletion of their data at any time.

## Refund policy (draft)

1. Refunds can be requested within 14 days of purchase.
2. Every refund is approved by the founder; a refund revokes access to the product.
3. Refunds go back through the original payment method — this prototype moves no money.
"""


def write(venture: dict, pricing: dict, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(venture, pricing), encoding="utf-8")
    return out_path
