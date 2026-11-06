# WardZero: Technical Architecture Document

> **Disclaimer**: Decision-support prototype. Synthetic data only. Not a medical device. Not clinically validated. All outputs are strictly decision-support suggestions, never medical diagnoses.

---

## 1. Problem Statement & Clinical Context

In remote patient monitoring (RPM) and hospital-at-home settings, clinical teams face two symmetric failures:
1. **Silent Physiological Deterioration**: Vitals often drift subtly over 12–48 hours before an overt crisis. Isolated spot-checks miss rolling velocity (slope) and variability.
2. **Alert Fatigue & False Alarms**: Unfiltered sensor artifacts (e.g., loose pulse oximeter probe) trigger panic alerts, while unanswered critical notifications fail to escalate across safety tiers.

**WardZero** addresses both challenges with a lightweight, explainable, and fault-tolerant decision-support pipeline tailored for home healthcare.

---

## 2. System Architecture

WardZero is intentionally built without heavy container orchestration or external message brokers:

```
+--------------------------------------------------------------------+
|                         Simulated Sensors                          |
|         (P001: Mr. Sharma [COPD], P002: Mrs. Anita Rao)            |
|       - 2-second telemetry packets (HR, SpO2, Sys/Dia, Temp)       |
|       - Local FIFO buffer for store-and-forward tolerance          |
+---------------------------------+----------------------------------+
                                  |
                           POST /ingest (HTTP)
                                  |
                                  v
+--------------------------------------------------------------------+
|                         FastAPI Backend                            |
|                                                                    |
|  [Ingestion & Data Quality]                                        |
|  - Idempotency & deduplication: (device_id, sequence_num)          |
|  - Out-of-bounds artifact detection (impossible values flagged     |
|    as "sensor issue", NOT emergency)                               |
|  - Heartbeat monitor: flag offline if no data > 15s                |
|                                                                    |
|  [Hybrid Risk Engine]                                              |
|  - Rule Score: inspired by NEWS2 (National Early Warning Score 2)   |
|  - ML Classifier: Scikit-learn Logistic Regression                |
|    predicting probability of 24-48h deterioration                  |
|  - Context Injector: baseline vitals, patient age/condition,       |
|    and free-text caregiver symptom keywords                        |
|  - Plain-English Explainability: feature value x coefficient       |
|  - Degraded Mode: seamless rule-based fallback if model offline     |
|                                                                    |
|  [Escalation & Notification Outbox]                                |
|  - Tiered SLA timer: Caregiver A (30s) -> Caregiver B -> Family    |
|    -> Recommend Medical Professional                               |
|  - Cooldown deduplication to avoid repetitive alarm fatigue        |
|  - Mock SMS/WhatsApp Notification Outbox                           |
+---------------------------------+----------------------------------+
                                  |
                      HTTP Polling (2-second interval)
                                  |
                                  v
+--------------------------------------------------------------------+
|                       Single-Page Frontend                         |
|  - Vanilla JS + Tailwind CSS (CDN) + Chart.js (CDN)                |
|  - 4 Vital KPI cards with mini sparklines                          |
|  - Dual-axis real-time SpO2 & Heart Rate trend chart               |
|  - Risk badge + 24-48h Deterioration Gauge + "Why?" reasons        |
|  - Caregiver response console (Acknowledge, On My Way, Resolved)   |
|  - Interactive Failure Demonstration Panel                         |
+--------------------------------------------------------------------+
```

---

## 3. Risk Assessment Approach

WardZero uses a **hybrid, explainable design** instead of a black-box deep learning system:

### A. NEWS2-Inspired Rules (Clinical Safety Floor)
- Evaluates immediate vitals against established physiological corridors:
  - **SpO2**: Calibrated specifically for COPD patients (target 88–92% hypercapnic risk curve vs non-COPD standard 94–98%).
  - **Heart Rate**: Flags marked tachycardia (>110 bpm) or severe bradycardia (<40 bpm).
  - **Blood Pressure & Temperature**: Assesses systolic deviations and fever/hypothermia.
- Outputs discrete tiers: `LOW`, `MODERATE`, `HIGH`, `CRITICAL`.
- *Note: Clearly labeled in all interfaces as "Inspired by NEWS2, not clinically validated".*

### B. Machine Learning (24–48h Forward Looking)
- **Model**: Scikit-Learn `LogisticRegression(class_weight="balanced")`.
- **Input Features**: Rolling statistics over window (mean SpO2, SpO2 slope, SpO2 standard deviation, mean HR, HR slope, HR std, mean Sys BP, Sys BP slope, caregiver symptom flag, age, COPD indicator).
- **Explainability**: No heavy SHAP or LIME dependencies. Explanations derive directly from the normalized feature value multiplied by the model coefficient ($\beta_i \cdot x_i$), ranking the top 3 plain English risk drivers.
- **Fail-Safe / Degraded Mode**: If `model.pkl` is missing or corrupted, the system falls back to rule-based evaluation and renders a prominent **"Degraded Mode: Operating under rule-based fallback"** banner.

### C. Contextual Integration
- Incorporates caregiver observations in real-time. Keyword matching for `breathless`, `dizzy`, `confused`, `not eating` directly elevates risk weighting.

---

## 4. Fault Tolerance & Failure Modes

1. **Network Disconnection (Store-and-Forward)**:
   - When the backend is unreachable (simulated via Failure Panel or actual connection loss), the simulator catches the exception, buffers readings into a local JSON store, and marks them with their original generation timestamps.
   - Upon network restoration, the buffer drains in chronological order (`FIFO`), and the backend deduplicates any overlapping packets.
2. **Sensor Hardware Failure**:
   - Out-of-range sensor readings (e.g. SpO2 < 40%, HR 0 bpm) are flagged as `Sensor Transmission Issue` rather than triggering a medical emergency escalation.
3. **Caregiver Unresponsiveness**:
   - Active alerts carry a 30-second acknowledgment timer. If unanswered, the alert automatically transitions from `Caregiver A` to `Caregiver B`, then to `Family`, and finally advises contact with emergency medical services.

---

## 5. Assumptions and Limitations

- **Synthetic Data**: Trained exclusively on synthetic distributions. Not suitable for actual clinical diagnosis.
- **Polling vs WebSockets**: Uses 2-second HTTP polling to maintain zero external dependencies and simplicity. In production, WebSockets or SSE would be preferred for high scale.
- **Local SQLite**: Demonstrates single-node edge persistence. Production deployments would utilize distributed time-series databases (e.g. TimescaleDB, InfluxDB).
- **Simulated Notifications**: SMS and WhatsApp messages are dispatched to an in-memory/DB outbox rather than an active Twilio gateway.

---

## 6. Future Roadmap

1. **HL7 / FHIR Integration**: Export observation logs as standard FHIR `Observation` and `CarePlan` resources.
2. **Bi-directional Wearable BLE Gateway**: Connect commercial Bluetooth LE pulse oximeters directly to the ingestion pipeline.
3. **Federated Model Fine-Tuning**: Allow on-device model adaptation without transmitting raw PII out of the home.

