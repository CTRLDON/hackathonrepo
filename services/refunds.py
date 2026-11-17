"""Refunds — MOCKED. A refund needs explicit founder approval, revokes access, and moves no money.

The system never refunds by itself: without approved_by="founder" the call is refused.
"""
from __future__ import annotations
from backend.approval_manager import ApprovalRequired
from services import delivery

MOCKED = True


def refund(store, order_id: str, *, approved_by: str | None, reason: str = "") -> dict:
    if approved_by != "founder":
        store.note(f"Refund for {order_id} refused — needs founder approval")
        raise ApprovalRequired(f"Refund of {order_id} requires founder approval")
    order = store.orders.get(order_id)
    if not order or order["status"] != "paid":
        raise ValueError(f"order {order_id} is not refundable")
    if order_id in store.refunds:
        store.note(f"Refund for {order_id} already recorded → not refunded twice")
        return store.refunds[order_id]
    rec = {"id": store.next_id("ref"), "order_id": order_id, "amount": order["price"],
           "approved_by": approved_by, "reason": reason, "mocked": True}
    store.refunds[order_id] = rec
    order["status"] = "refunded"
    store.note(f"MOCK refund {rec['id']} of {rec['amount']:.2f} for {order_id}, approved by founder")
    delivery.revoke(store, order_id)
    return rec
