"""
Hexagonal Ports (Abstract Interfaces) for AegisBridge-EMS.
Core domain layer: zero dependencies on external drivers or protocols.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Any
from src.domain.models import TriageUrgencyEnum


class PIISanitizerPort(ABC):
    @abstractmethod
    def sanitize_text(self, raw_text: str) -> tuple[str, list[dict[str, str]]]:
        """
        Sanitizes text before LLM inference using reversible token encryption.
        Returns: (sanitized_text, metadata_items)
        """
        pass

    @abstractmethod
    def restore_entity(self, anonymized_token: Optional[str]) -> str:
        """Restores encrypted token for authorized downstream clinical payloads."""
        pass


class AuditLedgerPort(ABC):
    @abstractmethod
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
        """Appends an RFC 2104 HMAC-SHA256 hash-chained audit entry."""
        pass

    @abstractmethod
    def verify_ledger(self) -> tuple[bool, int, list[str]]:
        """Verifies cryptographic hash chain integrity of the ledger."""
        pass
