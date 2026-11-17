"""Payments — MOCKED. No payment provider, no sandbox, no card data, and no money ever moves.

Simulates the sale-to-cash path so the architecture can be demonstrated and tested:
order → (mock) payment event → automatic delivery → optional founder-approved refund → reconciliation.
Payment events are idempotent: a replayed event id is recognised and never pays or delivers twice.
"""
from __future__ import annotations
from dataclasses import dataclass, field

MOCKED = True
# Illustrative processor fee used only to exercise reconciliation — ASSUMPTION, not a real quote.
FEE_RATE, FEE_FIXED = 0.029, 0.30


@dataclass
class MockStore:
    """In-memory ledger for one mocked run. Buyers are opaque references — no personal data."""
    orders: dict = field(default_factory=dict)
    payments: dict = field(default_factory=dict)      # payment id -> payment
    events_seen: dict = field(default_factory=dict)   # event id -> payment id (idempotency)
    access: dict = field(default_factory=dict)        # order id -> delivery record
    refunds: dict = field(default_factory=dict)
    log: list = field(default_factory=list)
    _n: int = 0

    def next_id(self, prefix):
        self._n += 1
        return f"{prefix}_{self._n:03d}"

    def note(self, line):
        self.log.append(line)


def create_order(store: MockStore, product: str, price: float, buyer_ref: str) -> dict:
    order = {"id": store.next_id("ord"), "product": product, "price": round(float(price), 2),
             "buyer_ref": buyer_ref, "status": "pending"}
    store.orders[order["id"]] = order
    store.note(f"Order {order['id']} created for {buyer_ref}: {product} at {order['price']:.2f} (status pending)")
    return order


def record_payment_event(store: MockStore, order_id: str, event_id: str, amount: float | None = None) -> dict:
    """Handle a (mock) 'payment succeeded' event. Payment triggers delivery; replays are no-ops."""
    from services import delivery
    if event_id in store.events_seen:
        store.note(f"Event {event_id} replayed → ignored (idempotent: no second payment, no second delivery)")
        return {"duplicate": True, "payment": store.payments[store.events_seen[event_id]]}
    order = store.orders.get(order_id)
    if not order:
        raise ValueError(f"unknown order {order_id}")
    amount = round(float(order["price"] if amount is None else amount), 2)
    fee = round(amount * FEE_RATE + FEE_FIXED, 2)
    pay = {"id": store.next_id("pay"), "order_id": order_id, "event_id": event_id,
           "amount": amount, "fee": fee, "status": "succeeded", "mocked": True}
    store.payments[pay["id"]] = pay
    store.events_seen[event_id] = pay["id"]
    store.note(f"Event {event_id}: MOCK payment {pay['id']} of {amount:.2f} for {order_id} (fee {fee:.2f})")
    if amount + 0.005 < order["price"]:
        order["status"] = "underpaid"
        store.note(f"{order_id} underpaid ({amount:.2f} of {order['price']:.2f}) → delivery held for founder review")
        return {"duplicate": False, "payment": pay}
    order["status"] = "paid"
    delivery.deliver(store, order_id)
    return {"duplicate": False, "payment": pay}
