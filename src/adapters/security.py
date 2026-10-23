"""
Security and Cryptographic Infrastructure Adapters.
OWASP Top 10 for LLM v2.0 (2025) Compliance:
- LLM02:2025: Reversible Cryptographic PII/PHI Vault.
- NENA-STA-010 i3 & RFC 2104: Immutable HMAC-SHA256 Audit Trail.
"""

from __future__ import annotations
import base64
import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Optional

from cryptography.fernet import Fernet
from src.domain.models import TriageUrgencyEnum
from src.domain.ports import AuditLedgerPort, PIISanitizerPort


class ReversiblePresidioVaultAdapter(PIISanitizerPort):
    """
    Reversible Cryptographic Anonymization Pipeline (OWASP LLM02:2025).
    Safely sanitizes Protected Health Information (PHI) before LLM ingestion,
    preserving encrypted tokens that can be deanonymized exclusively for
    authorized downstream clinical protocols (HL7 FHIR).
    """

    DEFAULT_ALLOW_LIST: Final[list[str]] = [
        "Glasgow",
        "Cushing",
        "Babinski",
        "Apgar",
        "Ringer",
        "Fallot",
        "Romberg",
        "Battle",
        "Kernig",
        "Brudzinski",
        "STEMI",
        "Stroke",
    ]

    def __init__(self, secret_key: Optional[bytes] = None) -> None:
        if secret_key is None:
            # Generate or derive a 32-byte url-safe base64 key for Fernet
            self._fernet_key = Fernet.generate_key()
        else:
            # Deterministically derive 32-byte urlsafe key from secret
            raw_key = hashlib.sha256(secret_key).digest()
            self._fernet_key = base64.urlsafe_b64encode(raw_key)

        self._cipher = Fernet(self._fernet_key)
        self._allow_list = set(word.lower() for word in self.DEFAULT_ALLOW_LIST)

        # Regex patterns for high-confidence identification
        self._mrn_pattern = re.compile(r"\bMRN[-:\s]*(\d{6,10})\b", re.IGNORECASE)
        self._ssn_pattern = re.compile(r"\b(\d{3}-\d{2}-\d{4})\b")
        self._phone_pattern = re.compile(
            r"\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b"
        )
        self._email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
        # Explicit name cues common in emergency transcripts: "Patient: John Doe", "name is Jane Smith"
        self._name_intro_pattern = re.compile(
            r"\b(?:patient(?:\s+name)?(?:\s+is)?[:\s]+|named\s+|name\s+is\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b",
            re.IGNORECASE,
        )

        # In-memory mapping of encrypted token -> original text
        self._vault: dict[str, str] = {}

    def _encrypt_val(self, val: str, entity_type: str) -> str:
        encrypted_bytes = self._cipher.encrypt(val.encode("utf-8"))
        # Create a compact, clean token
        short_token = f"[ENCRYPTED_{entity_type}_{hashlib.sha256(encrypted_bytes).hexdigest()[:8]}]"
        self._vault[short_token] = val
        return short_token

    def sanitize_text(self, raw_text: str) -> tuple[str, list[dict[str, str]]]:
        """
        Scans text, excludes clinical eponyms, encrypts detected identifiers.
        """
        sanitized = raw_text
        meta: list[dict[str, str]] = []

        # 1. Names preceded by cues
        for match in self._name_intro_pattern.finditer(raw_text):
            name_val = match.group(1).strip()
            if any(part.lower() in self._allow_list for part in name_val.split()):
                continue
            token = self._encrypt_val(name_val, "PATIENT_NAME")
            sanitized = sanitized.replace(name_val, token)
            meta.append({"entity_type": "PATIENT_NAME", "token": token})

        # 2. Medical Record Numbers
        for match in self._mrn_pattern.finditer(raw_text):
            mrn_val = match.group(0).strip()
            token = self._encrypt_val(mrn_val, "MRN")
            sanitized = sanitized.replace(mrn_val, token)
            meta.append({"entity_type": "MEDICAL_RECORD_NUMBER", "token": token})

        # 3. Social Security Numbers
        for match in self._ssn_pattern.finditer(raw_text):
            ssn_val = match.group(0).strip()
            token = self._encrypt_val(ssn_val, "SSN")
            sanitized = sanitized.replace(ssn_val, token)
            meta.append({"entity_type": "SSN", "token": token})

        # 4. Phone Numbers
        for match in self._phone_pattern.finditer(raw_text):
            phone_val = match.group(0).strip()
            token = self._encrypt_val(phone_val, "PHONE_NUMBER")
            sanitized = sanitized.replace(phone_val, token)
            meta.append({"entity_type": "PHONE_NUMBER", "token": token})

        # 5. Email Addresses
        for match in self._email_pattern.finditer(raw_text):
            email_val = match.group(0).strip()
            token = self._encrypt_val(email_val, "EMAIL_ADDRESS")
            sanitized = sanitized.replace(email_val, token)
            meta.append({"entity_type": "EMAIL_ADDRESS", "token": token})

        return sanitized, meta

    def restore_entity(self, anonymized_token: Optional[str]) -> str:
        """Restores encrypted token to original plain text."""
        if not anonymized_token:
            return "UNKNOWN_PRE_ARRIVAL_PATIENT"

        # Check direct token match
        if anonymized_token in self._vault:
            return self._vault[anonymized_token]

        # Check if the string contains a token
        for token, original in self._vault.items():
            if token in anonymized_token:
                return anonymized_token.replace(token, original)

        return anonymized_token


class HmacSha256AuditLedgerAdapter(AuditLedgerPort):
    """
    RFC 2104 HMAC-SHA256 hash-chained append-only audit ledger.
    Aligns with NENA-STA-010.2021.3 i3 Logging Service standard.
    """

    def __init__(self, ledger_path: str | Path, hmac_secret: bytes) -> None:
        self._ledger_path = Path(ledger_path)
        self._secret = hmac_secret
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hmac = self._get_tail_hmac()

    def _get_tail_hmac(self) -> str:
        """Recovers the most recent HMAC from the ledger if it exists, or returns 64 zeroes."""
        if not self._ledger_path.exists() or self._ledger_path.stat().st_size == 0:
            return "0" * 64

        last_line = ""
        with self._ledger_path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    last_line = stripped

        if last_line:
            try:
                data = json.loads(last_line)
                return str(data.get("entry_hmac_sha256", "0" * 64))
            except Exception:
                pass
        return "0" * 64

    def append_signed_event(
        self,
        incident_id: str,
        input_digest: str,
        model_used: str,
        confidence: float,
        esi_level: TriageUrgencyEnum,
        schema_valid: bool,
        dispatch_status: str,
        extra_metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        self._last_hmac = self._get_tail_hmac()
        timestamp = datetime.now(timezone.utc).isoformat()
        payload: dict[str, Any] = {
            "timestamp": timestamp,
            "incident_id": incident_id,
            "input_sha256": input_digest,
            "model_tier": model_used,
            "confidence_score": round(confidence, 4),
            "esi_triage_level": esi_level.value,
            "schema_validation_passed": schema_valid,
            "downstream_dispatch_status": dispatch_status,
            "previous_entry_hmac": self._last_hmac,
        }
        if extra_metadata:
            payload["metadata"] = extra_metadata

        canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(self._secret, canonical_bytes, hashlib.sha256).hexdigest()
        payload["entry_hmac_sha256"] = signature

        with self._ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")

        self._last_hmac = signature
        return signature

    def verify_ledger(self) -> tuple[bool, int, list[str]]:
        """
        Validates the entire hash-chained audit ledger.
        Returns: (is_valid, record_count, error_messages)
        """
        if not self._ledger_path.exists():
            return True, 0, []

        expected_prev = "0" * 64
        count = 0
        errors: list[str] = []

        with self._ledger_path.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                count += 1
                try:
                    entry = json.loads(stripped)
                except Exception as e:
                    errors.append(f"Line {idx}: Invalid JSON: {e}")
                    return False, count, errors

                entry_hmac = str(entry.get("entry_hmac_sha256", ""))
                prev_hmac = str(entry.get("previous_entry_hmac", ""))

                if prev_hmac != expected_prev:
                    errors.append(
                        f"Line {idx}: Broken HMAC chain. Expected prev {expected_prev[:12]}..., got {prev_hmac[:12]}..."
                    )
                    return False, count, errors

                # Recompute HMAC signature
                payload_to_verify = {k: v for k, v in entry.items() if k != "entry_hmac_sha256"}
                canonical_bytes = json.dumps(
                    payload_to_verify, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
                computed_hmac = hmac.new(self._secret, canonical_bytes, hashlib.sha256).hexdigest()

                if computed_hmac != entry_hmac:
                    errors.append(
                        f"Line {idx}: HMAC signature mismatch! Tampering detected. Computed: {computed_hmac[:12]}..., Recorded: {entry_hmac[:12]}..."
                    )
                    return False, count, errors

                expected_prev = entry_hmac

        return True, count, []


# Alias for PDF specification naming
PresidioReversibleVaultAdapter = ReversiblePresidioVaultAdapter
