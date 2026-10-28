import pytest
from event_ticket_tier import process_ticket_manifest, monitor_gate_flow


def test_single_general_order():
    manifests = [{"is_confirmed": True, "tier": "general",
                  "exclusive_lounge": False,
                  "orders": [{"qty": 2, "promo": ""}]}]
    result = process_ticket_manifest(manifests, 0.1)
    assert result["total_revenue"] == 99.0
    assert result["status"] == "COMPLETED"


def test_invalid_manifests_type():
    with pytest.raises(ValueError):
        process_ticket_manifest("abc", 0.1)


def test_unconfirmed_manifest_skipped():
    manifests = [{"is_confirmed": False, "tier": "vip",
                  "orders": [{"qty": 1, "promo": ""}]}]
    result = process_ticket_manifest(manifests, 0.1)
    assert result == {"total_revenue": 0.0, "status": "ZERO_SALES"}


def test_unknown_tier_rejected():
    manifests = [{"is_confirmed": True, "tier": "platinum",
                  "orders": [{"qty": 1, "promo": ""}]}]
    result = process_ticket_manifest(manifests, 0.1)
    assert result["status"] == "ZERO_SALES"


def test_zero_qty_rejected():
    manifests = [{"is_confirmed": True, "tier": "general",
                  "orders": [{"qty": 0, "promo": ""}]}]
    result = process_ticket_manifest(manifests, 0.0)
    assert result["status"] == "ZERO_SALES"


def test_vip_fraud_risk_breaks():
    manifests = [{"is_confirmed": True, "tier": "vip",
                  "orders": [{"qty": 1, "promo": ""},
                             {"qty": 1, "promo": "FRAUD_RISK"}]}]
    result = process_ticket_manifest(manifests, 0.1)
    assert result["status"] == "ZERO_SALES"


def test_earlybird_discount():
    manifests = [{"is_confirmed": True, "tier": "vip",
                  "orders": [{"qty": 1, "promo": "EARLYBIRD"}]}]
    result = process_ticket_manifest(manifests, 0.0)
    assert result["total_revenue"] == 120.0
    assert result["status"] == "COMPLETED"


def test_premium_bulk_with_lounge():
    manifests = [{"is_confirmed": True, "tier": "premium",
                  "exclusive_lounge": True,
                  "orders": [{"qty": 5, "promo": ""}]}]
    result = process_ticket_manifest(manifests, 0.0)
    assert result["total_revenue"] == 505.0  # 450 - 20 + 75
    assert result["status"] == "COMPLETED"


def test_audit_rejected():
    manifests = [{"is_confirmed": True, "tier": "general",
                  "orders": [{"qty": 0}] * 5}]
    result = process_ticket_manifest(manifests, 0.0)
    assert result["status"] == "AUDIT_REJECTED"


def test_gate_no_data():
    assert monitor_gate_flow([]) == "NO_DATA"


def test_gate_overflow():
    assert monitor_gate_flow([[60, 70]]) == "OVERFLOW"


def test_gate_normal():
    assert monitor_gate_flow([[10, 20]]) == "FLOW_NORMAL"