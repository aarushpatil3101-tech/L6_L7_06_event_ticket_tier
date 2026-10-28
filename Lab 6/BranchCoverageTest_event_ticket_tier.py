import pytest
from event_ticket_tier import process_ticket_manifest, monitor_gate_flow


def make(tier="general", orders=None, lounge=False, confirmed=True):
    return {"is_confirmed": confirmed, "tier": tier,
            "exclusive_lounge": lounge, "orders": orders or []}


# ---------- validation ----------
def test_invalid_manifests_type():
    with pytest.raises(ValueError):
        process_ticket_manifest("abc", 0.1)


def test_negative_tax_rate():
    with pytest.raises(ValueError):
        process_ticket_manifest([], -0.1)


def test_empty_manifests_list():
    result = process_ticket_manifest([], 0.1)
    assert result == {"total_revenue": 0.0, "status": "ZERO_SALES"}


# ---------- confirmation / defaults ----------
def test_unconfirmed_manifest_skipped():
    result = process_ticket_manifest(
        [make("vip", [{"qty": 1}], confirmed=False)], 0.1)
    assert result["status"] == "ZERO_SALES"


def test_missing_keys_default_to_general():
    # no tier -> general (45); orders without promo key
    result = process_ticket_manifest(
        [{"is_confirmed": True, "orders": [{"qty": 1}]}], 0.0)
    assert result == {"total_revenue": 45.0, "status": "COMPLETED"}


def test_manifest_missing_is_confirmed_skipped():
    result = process_ticket_manifest([{}], 0.0)
    assert result["status"] == "ZERO_SALES"


# ---------- tiers ----------
def test_general_order_with_tax():
    result = process_ticket_manifest(
        [make("general", [{"qty": 2, "promo": ""}])], 0.1)
    assert result == {"total_revenue": 99.0, "status": "COMPLETED"}


def test_vip_order():
    result = process_ticket_manifest([make("vip", [{"qty": 1}])], 0.0)
    assert result["total_revenue"] == 150.0


def test_premium_order():
    result = process_ticket_manifest([make("premium", [{"qty": 1}])], 0.0)
    assert result["total_revenue"] == 90.0


def test_unknown_tier_rejected():
    result = process_ticket_manifest([make("platinum", [{"qty": 1}])], 0.0)
    assert result["status"] == "ZERO_SALES"


# ---------- quantity / bulk boundary ----------
def test_zero_qty_rejected():
    result = process_ticket_manifest([make("general", [{"qty": 0}])], 0.0)
    assert result["status"] == "ZERO_SALES"


def test_qty_4_no_bulk_discount():
    result = process_ticket_manifest([make("general", [{"qty": 4}])], 0.0)
    assert result["total_revenue"] == 180.0


def test_qty_5_bulk_discount():
    result = process_ticket_manifest([make("general", [{"qty": 5}])], 0.0)
    assert result["total_revenue"] == 205.0  # 225 - 20


# ---------- promo codes ----------
def test_earlybird_discount():
    result = process_ticket_manifest(
        [make("vip", [{"qty": 1, "promo": "EARLYBIRD"}])], 0.0)
    assert result["total_revenue"] == 120.0


def test_vip_fraud_risk_breaks_and_zeroes():
    result = process_ticket_manifest(
        [make("vip", [{"qty": 1}, {"qty": 1, "promo": "FRAUD_RISK"}])], 0.1)
    assert result["status"] == "ZERO_SALES"


def test_non_vip_fraud_risk_no_break():
    # Current behaviour: order is counted as rejected but still billed.
    result = process_ticket_manifest(
        [make("general", [{"qty": 1, "promo": "FRAUD_RISK"}])], 0.0)
    assert result == {"total_revenue": 45.0, "status": "COMPLETED"}


# ---------- lounge / empty orders ----------
def test_lounge_fee_added():
    result = process_ticket_manifest(
        [make("premium", [{"qty": 5}], lounge=True)], 0.0)
    assert result["total_revenue"] == 505.0  # 450 - 20 + 75


def test_empty_orders_with_lounge():
    result = process_ticket_manifest([make("general", [], lounge=True)], 0.0)
    assert result == {"total_revenue": 75.0, "status": "COMPLETED"}


def test_empty_orders_no_lounge():
    result = process_ticket_manifest([make("general", [])], 0.0)
    assert result["status"] == "ZERO_SALES"


def test_multiple_manifests():
    result = process_ticket_manifest(
        [make("general", [{"qty": 1}]), make("vip", [{"qty": 1}])], 0.0)
    assert result["total_revenue"] == 195.0


# ---------- audit threshold ----------
def test_exactly_4_rejections_not_audit():
    orders = [{"qty": 0}] * 4 + [{"qty": 1}]
    result = process_ticket_manifest([make("general", orders)], 0.0)
    assert result == {"total_revenue": 45.0, "status": "COMPLETED"}


def test_5_rejections_audit_rejected():
    result = process_ticket_manifest(
        [make("general", [{"qty": 0}] * 5)], 0.0)
    assert result["status"] == "AUDIT_REJECTED"


# ---------- gate flow ----------
def test_gate_no_data():
    assert monitor_gate_flow([]) == "NO_DATA"


def test_gate_empty_stream():
    assert monitor_gate_flow([[]]) == "FLOW_NORMAL"


def test_gate_normal():
    assert monitor_gate_flow([[10, 20]]) == "FLOW_NORMAL"


def test_gate_boundary_50_not_congested():
    assert monitor_gate_flow([[50, 50]]) == "FLOW_NORMAL"


def test_gate_streak_resets():
    assert monitor_gate_flow([[60, 10, 60]]) == "FLOW_NORMAL"


def test_gate_overflow():
    assert monitor_gate_flow([[60, 70]]) == "OVERFLOW"


def test_gate_overflow_in_second_stream():
    assert monitor_gate_flow([[10, 20], [60, 70]]) == "OVERFLOW"