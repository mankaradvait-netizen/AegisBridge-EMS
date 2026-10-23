"""
Unit tests for Reversible Cryptographic PII Vault & HMAC-SHA256 Audit Ledger.
Verifies OWASP LLM02:2025 mitigation and RFC 2104 audit immutability.
"""

import json
from pathlib import Path
from src.adapters.security import HmacSha256AuditLedgerAdapter, ReversiblePresidioVaultAdapter
from src.domain.models import TriageUrgencyEnum


def test_pii_vault_anonymizes_sensitive_data():
    """Confirms PII entities (MRN, phone, patient name) are encrypted."""
    vault = ReversiblePresidioVaultAdapter()
    raw = "Patient: John Doe, MRN-884920, Phone: 412-555-0199 has chest pain."

    sanitized, meta = vault.sanitize_text(raw)
    assert "John Doe" not in sanitized
    assert "884920" not in sanitized
    assert "412-555-0199" not in sanitized
    assert "[ENCRYPTED_" in sanitized
    assert len(meta) >= 3


def test_pii_vault_preserves_clinical_eponyms():
    """Confirms diagnostic eponyms (Glasgow, Cushing, Babinski) are NOT stripped."""
    vault = ReversiblePresidioVaultAdapter()
    raw = "Patient scored 12 on Glasgow Coma Scale, positive Babinski sign, Cushing triad observed."

    sanitized, _ = vault.sanitize_text(raw)
    assert "Glasgow" in sanitized
    assert "Babinski" in sanitized
    assert "Cushing" in sanitized


def test_pii_vault_restores_original_for_fhir():
    """Confirms deanonymization accurately recovers original patient identity for FHIR."""
    vault = ReversiblePresidioVaultAdapter()
    raw = "Patient: Sarah Connor, MRN-994123."
    sanitized, meta = vault.sanitize_text(raw)
    assert len(sanitized) > 0

    for item in meta:
        token = item["token"]
        restored = vault.restore_entity(token)
        assert restored in ("Sarah Connor", "MRN-994123")


def test_hmac_audit_chain_tamper_detection(tmp_path: Path):
    """Verifies that tampering with an audit record breaks the cryptographic chain."""
    ledger_path = tmp_path / "test_audit.jsonl"
    secret = b"TestSuperSecret2026"
    adapter = HmacSha256AuditLedgerAdapter(ledger_path=ledger_path, hmac_secret=secret)

    # Append two valid events
    adapter.append_signed_event(
        incident_id="INC-001",
        input_digest="a" * 64,
        model_used="gemini-2.5-flash",
        confidence=0.95,
        esi_level=TriageUrgencyEnum.ESI_2_EMERGENT,
        schema_valid=True,
        dispatch_status="QUEUED_FOR_HITL_CONFIRMATION",
    )
    adapter.append_signed_event(
        incident_id="INC-002",
        input_digest="b" * 64,
        model_used="gemini-2.5-flash",
        confidence=0.98,
        esi_level=TriageUrgencyEnum.ESI_1_CRITICAL,
        schema_valid=True,
        dispatch_status="QUEUED_FOR_HITL_CONFIRMATION",
    )

    is_valid, count, errors = adapter.verify_ledger()
    assert is_valid is True
    assert count == 2
    assert len(errors) == 0

    # Tamper with first record (change triage level)
    lines = ledger_path.read_text(encoding="utf-8").strip().split("\n")
    record0 = json.loads(lines[0])
    record0["esi_triage_level"] = "ESI_5_NON_URGENT"  # Malicious alteration
    lines[0] = json.dumps(record0)
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid_after, count_after, errors_after = adapter.verify_ledger()
    assert is_valid_after is False
    assert count_after == 1
    assert any("mismatch" in e.lower() or "broken" in e.lower() for e in errors_after)
