"""Delivery — MOCKED. Grants access to the digital product only after a confirmed (mock) payment.

Idempotent per order: delivering twice returns the existing access instead of issuing a second one.
Nothing is emailed or sent; the access token is a local placeholder.
"""
from __future__ import annotations
import hashlib

MOCKED = True


def deliver(store, order_id: str) -> dict:
    order = store.orders[order_id]
    if order["status"] != "paid":
        raise ValueError(f"order {order_id} is {order['status']} — delivery needs a confirmed payment")
    if order_id in store.access:
        store.note(f"Delivery for {order_id} already granted → not delivered again")
        return store.access[order_id]
    token = "mock-" + hashlib.sha256(order_id.encode()).hexdigest()[:10]
    rec = {"order_id": order_id, "token": token, "active": True, "mocked": True}
    store.access[order_id] = rec
    store.note(f"Delivered {order['product']} for {order_id}: access token {token} (MOCKED, nothing sent)")
    return rec


def revoke(store, order_id: str) -> None:
    rec = store.access.get(order_id)
    if rec and rec["active"]:
        rec["active"] = False
        store.note(f"Access {rec['token']} for {order_id} revoked")


def has_access(store, order_id: str) -> bool:
    rec = store.access.get(order_id)
    return bool(rec and rec["active"])
