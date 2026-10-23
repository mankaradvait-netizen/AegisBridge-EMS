# AegisBridge-EMS

**Pre-Hospital NG911 & Trauma Center Multimodal Interoperability Bridge**  
*Built for the Gemini Societal-Benefit Challenge with the ThoughtStream Design System.*

---

## Overview

During the "Golden Hour" of acute medical emergencies—such as Out-of-Hospital Cardiac Arrest, STEMI, Acute Stroke, and Severe Trauma—patient survival depends on how rapidly field intelligence reaches the receiving Emergency Department (ED) and 911 Computer-Aided Dispatch (CAD).

**AegisBridge-EMS** acts as a zero-friction, life-saving bridge between chaotic, unstructured pre-hospital field inputs (ambient voice memos with sirens, photos of crushed pill bottles and vehicular crash scenes, asynchronous GPS and NOAA weather feeds) and rigid mission-critical downstream execution systems.

---

## Key Capabilities & Architectural Pillars

### 1. Neuro-Symbolic Clinical Safety Split
To eliminate the risk of LLM hallucinations dictating life-safety prioritization (OWASP LLM09:2025), AegisBridge-EMS separates multimodal perception from clinical classification:
- **Perception (Gemini 2.5 Flash / Pro)**: Extracts physiological vital signs, medication entities, and resource requirements from messy field inputs.
- **Classification (Deterministic ESI v4 Engine)**: Evaluates a 100% deterministic 4-step Emergency Severity Index decision tree (ESI Level 1 Resuscitation to ESI Level 5 Non-Urgent) with zero probabilistic drift.

### 2. Zero-Trust Security & OWASP Top 10 for LLM (v2.0 2025)
- **LLM01:2025 (Multimodal Prompt Injection Defense)**: Enforces structural separation via system instructions; wraps all untrusted field evidence inside `<untrusted_field_evidence>` delimiters; flags typographic and acoustic injection attempts without crashing.
- **LLM02:2025 (Reversible PII/PHI Cryptographic Vault)**: Scans and encrypts patient names, MRNs, SSNs, and phone numbers before LLM inference, while preserving vital clinical eponyms (*Glasgow*, *Cushing*, *Babinski*, *Apgar*, *Ringer*). Decrypts exclusively for authorized downstream HL7 FHIR Patient resources.
- **LLM06:2025 (Excessive Agency & HITL Gate)**: All ESI Level 1 (Critical) and Level 2 (Emergent) dispatches require a Human-in-the-Loop confirmation gate with a 10-second one-tap approval / override countdown.
- **Cryptographic Auditability (RFC 2104 HMAC-SHA256)**: Implements an append-only, tamper-evident hash-chained audit ledger (`audit_trail.jsonl`) aligned with the NENA-STA-010 i3 Logging Service standard.

### 3. Accredited Downstream Standards
1. **ANSI/NENA-STA-021.1b EIDO JSON**: Generates accredited Emergency Incident Data Objects with globally unique `$id` URNs (`urn:emergency:uid:eidodatacomponent:...`), W3C timestamps, WGS84 coordinates, and hazard classifications conveyed over NENA-STA-024.1.1 WebSockets (`emergency-ent` subprotocol).
2. **HL7 FHIR R4 Transaction Bundle (IHE mPSC Profile)**: Generates standard Patient, Encounter, Observation, and MedicationStatement resources mapped from NEMSIS v3.5.0 elements with LOINC panels (87825-6, 8867-4, 2708-6), SNOMED-CT, ICD-10-CM, RxNorm, and NEMSIS Pertinent Negatives.

### 4. ThoughtStream Design System Aesthetics
- **Minimal, Zen, Distraction-Free**: Warm neutral palette (Stone `#78716C`, Sage `#A8A29E`, Warm Black `#1C1917`, Warm White `#FAFAF9`, Surface `#F5F5F4`).
- **Sharp Geometric Precision**: 0px border radius across all cards, buttons, chips, and inputs (9999px strictly for avatars). Completely flat (0 shadows); separation via `#E7E5E4` hairline borders.
- **Typography**: Display/Headings in `Libre Baskerville` serif, UI/Body in `Inter`, Code in `Source Code Pro`. Max reading measure of 680px for readable prose.
- **WCAG 2.1 AAA High-Contrast Disaster Mode**: 1-click toggle to `#0A0A0A` canvas with `#FFFFFF` text (>= 7:1 contrast ratio) and neon emergency accents for smoke, rain, or low-light field conditions.
- **Gloved Touch Target Mode**: Expands touch targets to >= 56x56px for paramedics in heavy protective gloves.

---

## Directory Structure (Clean Hexagonal Architecture)

```
newpromptwars 2/
├── src/
│   ├── domain/
│   │   ├── models.py         # Pure domain entities, Pydantic schemas, Deterministic ESI v4 Engine
│   │   └── ports.py          # Abstract interfaces (PIISanitizerPort, AuditLedgerPort)
│   ├── adapters/
│   │   ├── security.py       # Reversible AES PII Vault & RFC 2104 HMAC-SHA256 Audit Ledger
│   │   ├── downstream.py     # ANSI/NENA EIDO JSON & HL7 FHIR R4 / NEMSIS v3.5.0 Builders
│   │   └── orchestrator.py   # Gemini Multimodal Orchestrator, Tiered Routing & Safety Gating
│   ├── api.py                # FastAPI server (REST, NENA emergency-ent WebSockets, Static Files)
│   └── static/
│       ├── index.html        # ThoughtStream Semantic HTML5 UI
│       ├── style.css         # ThoughtStream CSS design tokens & Disaster Mode
│       ├── app.js            # Frontend logic, Web Audio visualizer, HITL gate countdown
│       ├── sw.js             # Service Worker for offline-first PWA resilience
│       └── manifest.json     # PWA manifest
├── tests/
│   ├── unit/                 # Unit tests (ESI Engine, PII Vault, HMAC chain, API endpoints)
│   ├── schema_drift/         # Interoperability tests (NENA URN regex, FHIR transaction)
│   └── adversarial/          # Stress tests (OWASP prompt injection, cross-modal contradiction)
├── run.py                    # Application launcher
└── requirements.txt
```

---

## Running the Application

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Test Suite
```bash
python -m pytest -v
```
*(Runs 18 comprehensive tests verifying unit logic, schema drift, and adversarial defenses.)*

### 3. Launch Application Server
```bash
python run.py
```
Open **`http://127.0.0.1:8000`** in your browser.

---

## Gemini API Key Configuration (Zero-Trust Server-Side)
- Set the `GEMINI_API_KEY` environment variable in your server environment:
  ```bash
  # Windows PowerShell
  $env:GEMINI_API_KEY="AIzaSy..."
  # Linux / macOS
  export GEMINI_API_KEY="AIzaSy..."
  ```
- If left blank or unset, AegisBridge-EMS automatically operates in **Clinical High-Fidelity Simulator Mode**, enabling offline execution and instant interactive evaluation without client-side key exposure.
