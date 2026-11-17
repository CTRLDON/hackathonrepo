"""Store page — MOCKED. Rendered locally from the launch copy; never published anywhere.

`publish()` is the only way out, and it refuses unless the founder approved the Launch gate
(approval_manager.require_approved). Even then it only records a MOCKED publish — no post, no page.
"""
from __future__ import annotations
import html
from pathlib import Path

from backend import approval_manager

MOCKED = True


def render(venture: dict, materials: dict, pricing: dict | None = None) -> str:
    e = lambda s: html.escape(str(s or ""))  # noqa: E731
    name = (venture.get("brief") or {}).get("name") or venture.get("name") or "Your product"
    price = (pricing or {}).get("price_per_unit")
    unit = (pricing or {}).get("unit", "unit")
    claims = [c.get("text", "") for c in materials.get("claims", []) if c.get("status") != "unsupported"]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(name)} — store page (MOCKED)</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;line-height:1.6">
<p style="background:#fef3c7;border:1px dashed #d97706;padding:10px;border-radius:8px"><strong>MOCKED store page.</strong>
Not published. No checkout: payments and delivery are simulated, and nothing is charged.</p>
<h1>{e(name)}</h1><p style="font-size:1.2em">{e(materials.get("tagline"))}</p>
<p>{e(materials.get("one_liner"))}</p>
<ul>{"".join(f"<li>{e(c)}</li>" for c in claims)}</ul>
<p><strong>{e(f"{price} per {unit}" if price else "Price set in Commercial setup")}</strong></p>
<button disabled>{e(materials.get("call_to_action") or "Join the waitlist")} (MOCKED)</button>
<p style="color:#666;font-size:.9em">No reviews, testimonials or countdowns are shown: we only show claims backed by evidence.</p>
</body></html>"""


def write(venture: dict, materials: dict, pricing: dict | None, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(venture, materials, pricing), encoding="utf-8")
    return out_path


def publish(vid: str) -> dict:
    """MOCKED publish, gated on the founder's Launch approval. Raises ApprovalRequired otherwise."""
    approval_manager.require_approved(vid, "launch_gate")
    return {"published": False, "mocked": True,
            "message": "MOCKED publish recorded. Nothing was posted or deployed."}
