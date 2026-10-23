"""
Unit tests for Deterministic ESI v4 Engine.
Verifies the 4-step decision tree across all 5 ESI triage urgency levels.
"""

from src.domain.models import (
    DeterministicESIEngine,
    ExtractedVitalsSchema,
    GeminiMultimodalExtractionSchema,
    TriageUrgencyEnum,
)


def test_step_a_life_saving_intervention():
    """Decision Point A: Immediate life-saving intervention yields ESI 1."""
    schema = GeminiMultimodalExtractionSchema(
        acoustic_and_visual_evidence_summary="Patient apneic and pulseless.",
        requires_immediate_life_saving_intervention=True,
        is_high_risk_or_severe_distress=True,
        projected_ed_resource_count=3,
        patient_vitals=ExtractedVitalsSchema(heart_rate_bpm=0, systolic_bp_mmhg=0),
    )
    esi, rationale = DeterministicESIEngine.evaluate_esi_level(schema)
    assert esi == TriageUrgencyEnum.ESI_1_CRITICAL
    assert "Step A" in rationale


def test_step_b_high_risk_situation():
    """Decision Point B: High risk situation (STEMI, acute stroke) yields ESI 2."""
    schema = GeminiMultimodalExtractionSchema(
        acoustic_and_visual_evidence_summary="Acute crushing chest pain, diaphoresis, STEMI.",
        requires_immediate_life_saving_intervention=False,
        is_high_risk_or_severe_distress=True,
        projected_ed_resource_count=3,
        patient_vitals=ExtractedVitalsSchema(heart_rate_bpm=88, systolic_bp_mmhg=130),
    )
    esi, rationale = DeterministicESIEngine.evaluate_esi_level(schema)
    assert esi == TriageUrgencyEnum.ESI_2_EMERGENT
    assert "Step B" in rationale


def test_step_b_cross_modal_contradiction_failsafe():
    """Decision Point B Fail-safe: Verbal statement contradicts severe distress -> ESI 2."""
    schema = GeminiMultimodalExtractionSchema(
        acoustic_and_visual_evidence_summary="Patient verbally claims 'I feel fine' while ECG shows VTach.",
        requires_immediate_life_saving_intervention=False,
        is_high_risk_or_severe_distress=False,
        cross_modal_contradiction_detected=True,
        projected_ed_resource_count=3,
        patient_vitals=ExtractedVitalsSchema(heart_rate_bpm=160),
    )
    esi, rationale = DeterministicESIEngine.evaluate_esi_level(schema)
    assert esi == TriageUrgencyEnum.ESI_2_EMERGENT
    assert "contradiction" in rationale.lower()


def test_step_c_zero_resources_esi_5():
    """Decision Point C: 0 ED resources yields ESI 5 (Routine)."""
    schema = GeminiMultimodalExtractionSchema(
        acoustic_and_visual_evidence_summary="Medication refill or minor rash, no danger vitals.",
        requires_immediate_life_saving_intervention=False,
        is_high_risk_or_severe_distress=False,
        projected_ed_resource_count=0,
        patient_vitals=ExtractedVitalsSchema(
            heart_rate_bpm=72,
            systolic_bp_mmhg=120,
            respiratory_rate_rpm=14,
            spo2_percentage=98,
        ),
    )
    esi, rationale = DeterministicESIEngine.evaluate_esi_level(schema)
    assert esi == TriageUrgencyEnum.ESI_5_NON_URGENT
    assert "Zero ED resources" in rationale


def test_step_c_one_resource_esi_4():
    """Decision Point C: Exactly 1 ED resource yields ESI 4 (Less Urgent)."""
    schema = GeminiMultimodalExtractionSchema(
        acoustic_and_visual_evidence_summary="Isolated ankle sprain, needs single x-ray.",
        requires_immediate_life_saving_intervention=False,
        is_high_risk_or_severe_distress=False,
        projected_ed_resource_count=1,
        patient_vitals=ExtractedVitalsSchema(
            heart_rate_bpm=75,
            systolic_bp_mmhg=122,
            respiratory_rate_rpm=16,
            spo2_percentage=99,
        ),
    )
    esi, rationale = DeterministicESIEngine.evaluate_esi_level(schema)
    assert esi == TriageUrgencyEnum.ESI_4_LESS_URGENT
    assert "one ed resource" in rationale.lower()


def test_step_d_danger_zone_vitals_tachycardia():
    """Decision Point D: HR > 100 bpm with >= 2 resources up-triages to ESI 2."""
    schema = GeminiMultimodalExtractionSchema(
        acoustic_and_visual_evidence_summary="Abdominal pain with fever and tachycardia.",
        requires_immediate_life_saving_intervention=False,
        is_high_risk_or_severe_distress=False,
        projected_ed_resource_count=2,
        patient_vitals=ExtractedVitalsSchema(
            heart_rate_bpm=118,  # > 100 danger zone
            systolic_bp_mmhg=110,
            respiratory_rate_rpm=18,
            spo2_percentage=97,
        ),
    )
    esi, rationale = DeterministicESIEngine.evaluate_esi_level(schema)
    assert esi == TriageUrgencyEnum.ESI_2_EMERGENT
    assert "Danger Zone" in rationale


def test_step_d_stable_vitals_esi_3():
    """Decision Point D: >= 2 resources with stable physiological vitals yields ESI 3 (Urgent)."""
    schema = GeminiMultimodalExtractionSchema(
        acoustic_and_visual_evidence_summary="Moderate lower quadrant pain, requires blood panel and CT scan.",
        requires_immediate_life_saving_intervention=False,
        is_high_risk_or_severe_distress=False,
        projected_ed_resource_count=2,
        patient_vitals=ExtractedVitalsSchema(
            heart_rate_bpm=82,
            systolic_bp_mmhg=124,
            respiratory_rate_rpm=16,
            spo2_percentage=98,
        ),
    )
    esi, rationale = DeterministicESIEngine.evaluate_esi_level(schema)
    assert esi == TriageUrgencyEnum.ESI_3_URGENT
    assert "stable physiological vitals" in rationale.lower()


def test_step_d_danger_zone_vitals_bradycardia_and_bradypnea():
    """Decision Point D: HR < 50 bpm or RR < 10 rpm with >= 2 resources up-triages to ESI 2."""
    schema = GeminiMultimodalExtractionSchema(
        acoustic_and_visual_evidence_summary="Weakness, symptomatic bradycardia.",
        requires_immediate_life_saving_intervention=False,
        is_high_risk_or_severe_distress=False,
        projected_ed_resource_count=2,
        patient_vitals=ExtractedVitalsSchema(
            heart_rate_bpm=42,  # < 50 bradycardia danger zone
            systolic_bp_mmhg=100,
            respiratory_rate_rpm=8,  # < 10 bradypnea danger zone
            spo2_percentage=95,
        ),
    )
    esi, rationale = DeterministicESIEngine.evaluate_esi_level(schema)
    assert esi == TriageUrgencyEnum.ESI_2_EMERGENT
    assert "Bradycardia" in rationale
    assert "Bradypnea" in rationale
