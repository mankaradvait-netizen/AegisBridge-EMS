"""
Schema Drift & Protocol Compliance Suite.
Verifies 100% compliance with ANSI/NENA-STA-021.1b EIDO JSON and HL7 FHIR R4 Transaction Bundles.
"""

import re
from src.adapters.downstream import DownstreamProtocolBuilder
from src.domain.models import (
    ClinicalMedicationEntry,
    ExtractedVitalsSchema,
    GeminiMultimodalExtractionSchema,
    TriageUrgencyEnum,
)


def test_nena_eido_structure_and_urn():
    """Validates ANSI/NENA-STA-021.1b $id URN formatting and W3C timestamp."""
    extraction = GeminiMultimodalExtractionSchema(
        acoustic_and_visual_evidence_summary="Rollover collision on I-90 with multiple injuries.",
        requires_immediate_life_saving_intervention=True,
        is_high_risk_or_severe_distress=True,
        projected_ed_resource_count=3,
        scene_hazards_identified=["Fuel spill", "Downed lines"],
    )
    eido = DownstreamProtocolBuilder.build_nena_eido_payload(
        incident_id="test-incident-uuid-1234",
        agency_domain="idx.psap.allegheny.pa.us",
        extraction=extraction,
        esi_level=TriageUrgencyEnum.ESI_1_CRITICAL,
        lat=40.440624,
        lng=-79.995888,
    )

    assert eido["eidoVersion"] == "1.1b"
    assert "incidentComponent" in eido
    inc_comp = eido["incidentComponent"][0]

    # Verify $id URN pattern per NENA-STA-021.1b
    urn_pattern = re.compile(r"^urn:emergency:uid:eidodatacomponent:[a-zA-Z0-9]+:idx\.psap\.allegheny\.pa\.us$")
    assert urn_pattern.match(inc_comp["$id"]), f"URN did not match: {inc_comp['$id']}"

    # Verify W3C timestamp (YYYY-MM-DDTHH:MM:SSZ)
    w3c_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    assert w3c_pattern.match(inc_comp["lastUpdateTimeStamp"])

    # Verify WGS84 coordinate location
    loc_comp = eido["locationComponent"][0]
    coords = loc_comp["locationByValue"]["coordinate"]
    assert coords["datum"] == "WGS84"
    assert coords["latitude"] == 40.440624
    assert coords["longitude"] == -79.995888


def test_hl7_fhir_r4_bundle_transaction():
    """Validates HL7 FHIR R4 Transaction Bundle structure and clinical coding."""
    extraction = GeminiMultimodalExtractionSchema(
        acoustic_and_visual_evidence_summary="STEMI patient with crushing chest pain.",
        estimated_age_years=62,
        patient_vitals=ExtractedVitalsSchema(
            heart_rate_bpm=110,
            systolic_bp_mmhg=88,
            diastolic_bp_mmhg=54,
            respiratory_rate_rpm=22,
            spo2_percentage=91,
        ),
        primary_symptom_icd10="R07.9",
        provider_impression_icd10="I21.3",
        current_medications=[
            ClinicalMedicationEntry(
                medication_name="Apixaban",
                rxnorm_code="1364430",
                dosage_text="5mg Oral Tablet",
            )
        ],
    )

    bundle = DownstreamProtocolBuilder.build_hl7_fhir_r4_bundle(
        incident_id="incident-xyz-789",
        patient_display_id="Robert Vance",
        extraction=extraction,
        esi_level=TriageUrgencyEnum.ESI_2_EMERGENT,
    )

    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "transaction"
    entries = bundle["entry"]
    assert len(entries) >= 4  # Patient, Encounter, Observation, MedicationStatement

    # Check Patient resource
    patient_entry = next(e for e in entries if e["resource"]["resourceType"] == "Patient")
    assert patient_entry["resource"]["identifier"][0]["value"] == "Robert Vance"
    age_ext = patient_entry["resource"]["extension"][0]
    assert age_ext["url"] == "http://nemsis.org/fhir/StructureDefinition/ePatient-15-Age"
    assert age_ext["valueInteger"] == 62

    # Check Encounter resource
    encounter_entry = next(e for e in entries if e["resource"]["resourceType"] == "Encounter")
    assert encounter_entry["resource"]["priority"]["text"] == "ESI_2_EMERGENT"
    assert encounter_entry["resource"]["reasonCode"][0]["coding"][0]["code"] == "I21.3"

    # Check Observation resource (LOINC Panel)
    obs_entry = next(e for e in entries if e["resource"]["resourceType"] == "Observation")
    assert obs_entry["resource"]["code"]["coding"][0]["code"] == "87825-6"
    components = obs_entry["resource"]["component"]
    # Verify LOINC codes for vitals
    codes = [c["code"]["coding"][0]["code"] for c in components]
    assert "8867-4" in codes  # Heart rate
    assert "2708-6" in codes  # SpO2
    assert "8480-6" in codes  # Systolic BP


def test_hl7_fhir_r4_bundle_handles_missing_age():
    """Validates that FHIR bundle omits age extension rather than producing invalid valueInteger: null."""
    extraction = GeminiMultimodalExtractionSchema(
        acoustic_and_visual_evidence_summary="Unresponsive trauma patient, age unknown.",
        estimated_age_years=None,
        patient_vitals=ExtractedVitalsSchema(),
    )
    bundle = DownstreamProtocolBuilder.build_hl7_fhir_r4_bundle(
        incident_id="incident-no-age-123",
        patient_display_id="UNKNOWN_PRE_ARRIVAL_PATIENT",
        extraction=extraction,
        esi_level=TriageUrgencyEnum.ESI_1_CRITICAL,
    )
    patient_entry = next(e for e in bundle["entry"] if e["resource"]["resourceType"] == "Patient")
    assert "extension" not in patient_entry["resource"]
