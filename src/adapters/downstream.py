"""
Downstream Interoperability Protocol Builders.
ANSI/NENA-STA-021.1b EIDO JSON & HL7 FHIR R4 Transaction Bundle (NEMSIS v3.5.0).
"""

from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Final

from src.domain.models import GeminiMultimodalExtractionSchema, TriageUrgencyEnum


class DownstreamProtocolBuilder:
    """
    Translates validated clinical domain extractions into accredited
    emergency public safety and healthcare interoperability payloads.
    """

    MAX_EIDO_BYTES: Final[int] = 10_485_760  # NENA-STA-024.1.1 10 MB limit

    @classmethod
    def build_nena_eido_payload(
        cls,
        incident_id: str,
        agency_domain: str,
        extraction: GeminiMultimodalExtractionSchema,
        esi_level: TriageUrgencyEnum,
        lat: float,
        lng: float,
    ) -> dict[str, Any]:
        """
        Builds an ANSI/NENA-STA-021.1b compliant Emergency Incident Data Object (EIDO) JSON.
        """
        w3c_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        clean_inc_id = incident_id.replace("-", "")[:12]
        component_urn = f"urn:emergency:uid:eidodatacomponent:{clean_inc_id}:{agency_domain}"
        loc_urn = f"urn:emergency:uid:eidodatacomponent:loc{clean_inc_id[:8]}:{agency_domain}"
        note_urn = f"urn:emergency:uid:eidodatacomponent:note{clean_inc_id[:8]}:{agency_domain}"

        eido_object: dict[str, Any] = {
            "eidoVersion": "1.1b",
            "issuingElementIdentification": f"aegisbridge.{agency_domain}",
            "incidentComponent": [
                {
                    "$id": component_urn,
                    "lastUpdateTimeStamp": w3c_now,
                    "incidentTypeCommonRegistryText": "EMS_MEDICAL_TRAUMA",
                    "emergencyIncidentPriority": esi_level.value,
                    "externalIncidentIdentifier": incident_id,
                    "incidentTrackingIdentifier": f"TRK-{clean_inc_id.upper()}",
                }
            ],
            "locationComponent": [
                {
                    "$id": loc_urn,
                    "lastUpdateTimeStamp": w3c_now,
                    "locationByValue": {
                        "coordinate": {
                            "latitude": round(lat, 6),
                            "longitude": round(lng, 6),
                            "datum": "WGS84",
                        }
                    },
                }
            ],
            "notesComponent": [
                {
                    "$id": note_urn,
                    "lastUpdateTimeStamp": w3c_now,
                    "noteText": extraction.acoustic_and_visual_evidence_summary,
                    "hazardsIdentified": extraction.scene_hazards_identified,
                    "primaryImpressionICD10": extraction.provider_impression_icd10,
                }
            ],
        }

        serialized = json.dumps(eido_object).encode("utf-8")
        if len(serialized) > cls.MAX_EIDO_BYTES:
            raise ValueError(
                f"Generated EIDO exceeds NENA-STA-024 10MB limit ({len(serialized)} bytes)."
            )

        return eido_object

    @classmethod
    def build_hl7_fhir_r4_bundle(
        cls,
        incident_id: str,
        patient_display_id: str,
        extraction: GeminiMultimodalExtractionSchema,
        esi_level: TriageUrgencyEnum,
    ) -> dict[str, Any]:
        """
        Builds an HL7 FHIR R4 Transaction Bundle mapped from NEMSIS v3.5.0 elements.
        Complies with IHE mobile Paramedicine Summary of Care (mPSC) profile (PCC-1 transaction).
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        patient_urn = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_OID, incident_id + ':patient')}"
        encounter_urn = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_OID, incident_id + ':encounter')}"
        obs_urn = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_OID, incident_id + ':vitals')}"

        vitals_components: list[dict[str, Any]] = []
        v = extraction.patient_vitals

        # LOINC 8867-4: Heart rate
        if v.heart_rate_bpm is not None:
            vitals_components.append(
                {
                    "code": {
                        "coding": [
                            {"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"}
                        ]
                    },
                    "valueQuantity": {
                        "value": v.heart_rate_bpm,
                        "unit": "beats/min",
                        "system": "http://unitsofmeasure.org",
                        "code": "/min",
                    },
                }
            )

        # LOINC 2708-6: SpO2
        if v.spo2_percentage is not None:
            vitals_components.append(
                {
                    "code": {
                        "coding": [
                            {"system": "http://loinc.org", "code": "2708-6", "display": "Oxygen saturation"}
                        ]
                    },
                    "valueQuantity": {
                        "value": v.spo2_percentage,
                        "unit": "%",
                        "system": "http://unitsofmeasure.org",
                        "code": "%",
                    },
                }
            )

        # LOINC 8480-6: Systolic BP
        if v.systolic_bp_mmhg is not None:
            vitals_components.append(
                {
                    "code": {
                        "coding": [
                            {"system": "http://loinc.org", "code": "8480-6", "display": "Systolic blood pressure"}
                        ]
                    },
                    "valueQuantity": {
                        "value": v.systolic_bp_mmhg,
                        "unit": "mmHg",
                        "system": "http://unitsofmeasure.org",
                        "code": "mm[Hg]",
                    },
                }
            )

        # LOINC 8462-4: Diastolic BP
        if v.diastolic_bp_mmhg is not None:
            vitals_components.append(
                {
                    "code": {
                        "coding": [
                            {"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic blood pressure"}
                        ]
                    },
                    "valueQuantity": {
                        "value": v.diastolic_bp_mmhg,
                        "unit": "mmHg",
                        "system": "http://unitsofmeasure.org",
                        "code": "mm[Hg]",
                    },
                }
            )

        # LOINC 9279-1: Respiratory rate
        if v.respiratory_rate_rpm is not None:
            vitals_components.append(
                {
                    "code": {
                        "coding": [
                            {"system": "http://loinc.org", "code": "9279-1", "display": "Respiratory rate"}
                        ]
                    },
                    "valueQuantity": {
                        "value": v.respiratory_rate_rpm,
                        "unit": "breaths/min",
                        "system": "http://unitsofmeasure.org",
                        "code": "/min",
                    },
                }
            )

        # If vitals were empty or not recorded, document NEMSIS Pertinent Negative
        if not vitals_components:
            vitals_components.append(
                {
                    "code": {
                        "coding": [
                            {"system": "http://nemsis.org/v3", "code": v.vitals_status.value, "display": "Vitals Status"}
                        ]
                    },
                    "dataAbsentReason": {
                        "coding": [
                            {"system": "http://terminology.hl7.org/CodeSystem/data-absent-reason", "code": "unsupported"}
                        ]
                    },
                }
            )

        patient_resource: dict[str, Any] = {
            "resourceType": "Patient",
            "identifier": [
                {"system": "urn:aegis:prearrival", "value": patient_display_id}
            ],
        }
        if extraction.estimated_age_years is not None:
            patient_resource["extension"] = [
                {
                    "url": "http://nemsis.org/fhir/StructureDefinition/ePatient-15-Age",
                    "valueInteger": extraction.estimated_age_years,
                }
            ]

        entries: list[dict[str, Any]] = [
            {
                "fullUrl": patient_urn,
                "resource": patient_resource,
                "request": {"method": "POST", "url": "Patient"},
            },
            {
                "fullUrl": encounter_urn,
                "resource": {
                    "resourceType": "Encounter",
                    "status": "in-progress",
                    "class": {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                        "code": "EMER",
                        "display": "emergency",
                    },
                    "priority": {
                        "coding": [
                            {
                                "system": "urn:emergency:severity:esi",
                                "code": esi_level.name,
                                "display": esi_level.value,
                            }
                        ],
                        "text": esi_level.value,
                    },
                    "subject": {"reference": patient_urn},
                    "reasonCode": [
                        {
                            "coding": [
                                {
                                    "system": "http://hl7.org/fhir/sid/icd-10-cm",
                                    "code": extraction.provider_impression_icd10,
                                }
                            ]
                        }
                    ],
                },
                "request": {"method": "POST", "url": "Encounter"},
            },
            {
                "fullUrl": obs_urn,
                "resource": {
                    "resourceType": "Observation",
                    "status": "preliminary",
                    "code": {
                        "coding": [
                            {
                                "system": "http://loinc.org",
                                "code": "87825-6",
                                "display": "National Trauma Data Standard Panel",
                            }
                        ]
                    },
                    "subject": {"reference": patient_urn},
                    "encounter": {"reference": encounter_urn},
                    "effectiveDateTime": now_iso,
                    "component": vitals_components,
                },
                "request": {"method": "POST", "url": "Observation"},
            },
        ]

        # Add medication statements if identified
        for idx, med in enumerate(extraction.current_medications):
            med_urn = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_OID, f'{incident_id}:med:{idx}')}"
            entries.append(
                {
                    "fullUrl": med_urn,
                    "resource": {
                        "resourceType": "MedicationStatement",
                        "status": "active",
                        "medicationCodeableConcept": {
                            "coding": [
                                {
                                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                                    "code": med.rxnorm_code,
                                    "display": med.medication_name,
                                }
                            ],
                            "text": med.medication_name,
                        },
                        "subject": {"reference": patient_urn},
                        "note": [{"text": med.dosage_text}] if med.dosage_text else [],
                    },
                    "request": {"method": "POST", "url": "MedicationStatement"},
                }
            )

        return {
            "resourceType": "Bundle",
            "id": f"nemsis-prearrival-{incident_id[:12]}",
            "type": "transaction",
            "timestamp": now_iso,
            "entry": entries,
        }
