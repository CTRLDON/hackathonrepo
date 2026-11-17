"""MOCKED sale to cash: payment triggers delivery, idempotency, founder-approved refunds, reconciliation."""
import pytest

from backend.approval_manager import ApprovalRequired
from services import delivery, payments, reconcile, refunds


def test_payment_triggers_delivery_once():
    s = payments.MockStore()
    o = payments.create_order(s, "Template pack", 10, "buyer-1")
    with pytest.raises(ValueError):
        delivery.deliver(s, o["id"])  # no payment yet → no access
    payments.record_payment_event(s, o["id"], "evt_1")
    assert delivery.has_access(s, o["id"])
    assert payments.record_payment_event(s, o["id"], "evt_1")["duplicate"]
    assert len(s.payments) == 1 and len(s.access) == 1


def test_refund_needs_founder_and_revokes_access():
    s = payments.MockStore()
    o = payments.create_order(s, "Template pack", 10, "buyer-1")
    payments.record_payment_event(s, o["id"], "evt_1")
    with pytest.raises(ApprovalRequired):
        refunds.refund(s, o["id"], approved_by=None)
    assert delivery.has_access(s, o["id"])
    refunds.refund(s, o["id"], approved_by="founder")
    assert not delivery.has_access(s, o["id"])
    assert reconcile.reconcile(s)["balanced"]


def test_reconciliation_flags_mismatch():
    s = payments.MockStore()
    o = payments.create_order(s, "Template pack", 10, "buyer-1")
    payments.record_payment_event(s, o["id"], "evt_1", amount=7)
    rec = reconcile.reconcile(s)
    assert not rec["balanced"] and o["id"] in rec["issues"][0]


def test_payment_test_script_writes_log(tmp_path):
    from scripts.run_payment_test import run
    out = tmp_path / "payment_test_log.md"
    result = run(out)
    assert all(ok for _, ok in result["checks"])
    assert out.read_text().startswith("# Payment test log — MOCKED")
