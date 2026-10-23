"""
Integration tests for FastAPI endpoints.
Tests /api/config, /api/presets, /api/triage, /api/hitl/confirm, and /api/audit.
"""

from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)


def test_get_config():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "has_api_key" in data
    assert "tier1_model" in data


def test_get_presets():
    response = client.get("/api/presets")
    assert response.status_code == 200
    presets = response.json()
    assert len(presets) >= 5
    ids = [p["id"] for p in presets]
    assert "stemi-acute" in ids
    assert "polytrauma-crash" in ids


def test_triage_flow_and_hitl():
    # 1. Submit triage
    notes = "60-year-old male, crushing chest pain radiating to left arm, BP 82/50, pulse 128, SpO2 88%."
    resp = client.post(
        "/api/triage",
        data={
            "raw_field_notes": notes,
            "gps_lat": "40.440624",
            "gps_lng": "-79.995888",
        },
    )
    assert resp.status_code == 200
    triage_data = resp.json()
    incident_id = triage_data["incident_id"]
    assert triage_data["deterministic_esi_level"] in ("ESI_1_RESUSCITATION", "ESI_2_EMERGENT")
    assert triage_data["requires_hitl_approval"] is True
    assert "nena_sta_021_eido_payload" in triage_data
    assert "hl7_fhir_r4_nemsis_bundle" in triage_data

    # 2. Confirm HITL approval
    hitl_resp = client.post(
        "/api/hitl/confirm",
        json={
            "incident_id": incident_id,
            "action": "APPROVE",
            "dispatcher_id": "DISPATCHER-TEST",
        },
    )
    assert hitl_resp.status_code == 200
    hitl_data = hitl_resp.json()
    assert hitl_data["dispatch_status"] == "DISPATCHER_APPROVED_TRANSMITTED"

    # 3. Check audit log verification
    audit_resp = client.get("/api/audit")
    assert audit_resp.status_code == 200
    audit_data = audit_resp.json()
    assert audit_data["ledger_verified"] is True
    assert audit_data["entry_count"] >= 2


def test_security_protection_blocks_dotfiles():
    """Verifies that direct HTTP requests probing .env or internal configs are blocked with 403."""
    resp_env = client.get("/.env")
    assert resp_env.status_code == 403
    assert "Forbidden" in resp_env.text

    resp_git = client.get("/.git/config")
    assert resp_git.status_code == 403

    resp_pyproject = client.get("/pyproject.toml")
    assert resp_pyproject.status_code == 403


def test_get_config_zero_disclosure():
    """Verifies that /api/config returns boolean status and never leaks secret credentials."""
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["has_api_key"], bool)
    assert data["has_api_key"] is True
    # Ensure neither 'api_key' nor any secret string appears in the response
    assert "api_key" not in data
    assert "secret" not in data
