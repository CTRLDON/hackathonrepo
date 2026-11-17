"""Reconciliation — MOCKED data. Matches orders ↔ payments ↔ fees ↔ refunds ↔ payouts.

Flags: paid orders without a payment, payments whose amount differs from the order, deliveries
without payment, and refunded orders that still have active access.
"""
from __future__ import annotations

MOCKED = True


def reconcile(store) -> dict:
    by_order = {p["order_id"]: p for p in store.payments.values()}
    rows, issues = [], []
    for oid, o in store.orders.items():
        pay = by_order.get(oid)
        ref = store.refunds.get(oid)
        acc = store.access.get(oid)
        fee = pay["fee"] if pay else 0.0
        gross = pay["amount"] if pay else 0.0
        refunded = ref["amount"] if ref else 0.0
        payout = round(gross - fee - refunded, 2) if pay else 0.0
        rows.append({"order": oid, "status": o["status"], "price": o["price"], "paid": gross,
                     "fee": fee, "refunded": refunded, "payout": payout,
                     "access": "active" if acc and acc["active"] else ("revoked" if acc else "none")})
        if o["status"] in ("paid", "refunded") and not pay:
            issues.append(f"{oid}: marked {o['status']} but no payment found")
        if pay and abs(pay["amount"] - o["price"]) > 0.005:
            issues.append(f"{oid}: paid {pay['amount']:.2f} but order price is {o['price']:.2f}")
        if acc and acc["active"] and o["status"] != "paid":
            issues.append(f"{oid}: access active while order is {o['status']}")
    totals = {k: round(sum(r[k] for r in rows), 2) for k in ("paid", "fee", "refunded", "payout")}
    return {"rows": rows, "totals": totals, "issues": issues, "balanced": not issues, "mocked": True}
