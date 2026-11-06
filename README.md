# WardZero: Smart Home Healthcare Monitoring System

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-1.4.1-F7931E?logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-v3.x-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![Tests](https://img.shields.io/badge/Tests-PyTest%20Passing-brightgreen?logo=pytest&logoColor=white)](https://pytest.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**An Explainable, Fault-Tolerant Remote Patient Monitoring (RPM) Prototype**

[Key Features](#key-features) • [Architecture](#architecture) • [Quickstart](#quickstart) • [Demo Story](#demo-story) • [Failure Sandbox](#failure-demonstration-panel) • [Technical Specs](#technical-documentation)

</div>

---

> ⚠️ **Decision-Support Prototype Disclaimer**  
> WardZero is a technical research prototype developed for demonstration and hackathon evaluation purposes. It operates exclusively on synthetic physiological distributions and is **NOT** a certified medical device. It must **never** be used for clinical diagnosis or emergency medical decision-making.

---

## 📋 Table of Contents
- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Project Layout](#project-layout)
- [Quickstart Guide](#quickstart)
- [Running Automated Tests](#running-automated-tests)
- [3-Minute Demo Walkthrough](#demo-story)
- [Failure Sandbox & Resilience](#failure-demonstration-panel)
- [Clinical & ML Methodology](#clinical--ml-methodology)
- [License](#license)

---

## 🌟 Overview

In hospital-at-home and remote patient monitoring (RPM) setups, clinical safety is routinely compromised by two compounding issues:
1. **Silent Physiological Deterioration**: Clinical vital signs often drift subtly over 12–48 hours before an acute event. Isolated spot checks miss rolling trend velocities (slopes) and physiological variability.
2. **Alert Fatigue & Disconnection Vulnerability**: False alarms from noisy sensors overwhelm caretakers, while home network drops silently sever telemetry visibility.

**WardZero** solves both problems with a lightweight, explainable, and fault-tolerant telemetry pipeline. It ingests continuous multi-vital streams, performs hybrid risk evaluation (combining a **NEWS2-inspired clinical safety floor** with **Scikit-Learn Logistic Regression** for forward-looking 24–48h risk), executes multi-tier caregiver escalation SLAs, and provides store-and-forward tolerance against network outages.

---

## ⚡ Key Features

- **Continuous 2-Second Telemetry**: Real-time multi-parameter monitoring for heart rate, SpO2, blood pressure (systolic/diastolic), and body temperature.
- **Store-and-Forward Resilience**: Edge simulator queues packets in a local buffer during backend or network outages and replays them chronologically upon reconnection without data loss.
- **Data Quality & False Alarm Suppression**: Ingest pipeline identifies flatlines and out-of-range sensor artifacts, tagging them as `"sensor issue"` rather than triggering false emergency alerts.
- **Hybrid Explainable Risk Assessment**:
  - **Rule-based**: NEWS2-inspired scoring calibrated for baseline differences (e.g., hypercapnic COPD targets).
  - **Machine Learning**: Logistic regression forecasting probability of 24–48h deterioration using rolling statistics (mean, slope, variance).
  - **Explainability**: Direct $\beta_i \cdot x_i$ feature-contribution ranking explains the top 3 plain-English drivers behind every alert without heavy black-box libraries.
- **Caregiver Context Integration**: Natural language keyword detection (`breathless`, `dizzy`, `confused`, `not eating`) from notes dynamically updates the risk engine.
- **Multi-Tier Escalation SLA**: Automated failover across Caregiver A &rarr; Caregiver B &rarr; Family &rarr; Medical Professional if alerts remain unacknowledged.
- **Interactive Failure Panel**: Built-in edge-case sandbox to simulate network loss, corrupt telemetry packets, and unresponsive caregiver escalation in real time.
- **Modern Zero-Build Dashboard**: Clean, responsive glassmorphism UI built with vanilla JS, Tailwind CSS, and Chart.js via CDN (no Node.js/npm dependencies).

---

## 🏗️ System Architecture

```
+───────────────────────────────────────────────────────────────────+
│                        Edge Telemetry Source                      │
│        (P001: Mr. Sharma [COPD]  |  P002: Mrs. Anita Rao)         │
│         - Continuous 2s interval vitals                           │
│         - Local FIFO Store-and-Forward Buffer                     │
+─────────────────────────────────┬─────────────────────────────────+
                                  │ POST /ingest
                                  ▼
+───────────────────────────────────────────────────────────────────+
│                       FastAPI Telemetry Core                      │
│                                                                   │
│  [Ingestion & Data Quality]                                       │
│  - Idempotency deduplication: UNIQUE(device_id, sequence_num)     │
│  - Range validation (flags sensor artifacts vs medical anomalies) │
│  - Device heartbeat watchdog (offline alert if >15s silence)      │
│                                                                   │
│  [Hybrid Risk Engine]                                             │
│  - NEWS2-Inspired Safety Rules (discrete clinical floor)          │
│  - Scikit-Learn Logistic Regression (24-48h deterioration prob)   │
│  - Caregiver note keyword extractor & baseline adjuster           │
│  - Plain-English feature attribution (Beta x Scaled Feature)      │
│  - Degraded Mode: Rule fallback if model artifact unavailable     │
│                                                                   │
│  [Escalation SLA & Dispatcher]                                    │
│  - 30-second acknowledgment escalation timer                      │
│  - Per-patient cooldown to prevent alarm fatigue                  │
│  - Mock Notification Outbox (Simulated SMS / WhatsApp)            │
+─────────────────────────────────┬─────────────────────────────────+
                                  │ HTTP Polling (2-second sync)
                                  ▼
+───────────────────────────────────────────────────────────────────+
│                     Responsive Web Dashboard                      │
│  - Live vital metric cards with interactive sparklines            │
│  - Dual-axis SpO2 & Heart Rate trend chart                        │
│  - Risk gauge, plain-English "Why?" explanation block             │
│  - Caregiver response console & observation timeline              │
│  - Edge-case failure demonstration sandbox                        │
+───────────────────────────────────────────────────────────────────+
```

---

## 📁 Project Layout

```
.
├── backend/
│   ├── main.py              # FastAPI endpoints, static file server, data ingest
│   ├── db.py                # SQLite persistence, schema migrations, patient seeds
│   ├── risk.py              # NEWS2 rules, scikit-learn inference, explainability
│   └── alerts.py            # SLA escalation engine, cooldown, notification outbox
├── ml/
│   ├── generate_data.py     # Generates synthetic longitudinal vital statistics
│   ├── train.py             # Trains Logistic Regression classifier, outputs AUROC
│   └── model.pkl            # Serialized model & StandardScaler bundle
├── simulator/
│   └── simulator.py         # 2-patient simulator with store-and-forward buffer
├── frontend/
│   └── index.html           # Single-page modern dashboard (Tailwind + Chart.js)
├── docs/
│   ├── TECHNICAL_DOCUMENT.md # Engineering architecture, clinical models, roadmap
│   └── DEMO_SCRIPT.md        # 3-minute hackathon judge walkthrough
├── tests/
│   └── test_wardzero.py      # Automated PyTest suite (6 integration & unit tests)
├── requirements.txt         # Pinned Python package dependencies
├── run.sh                   # Unix/macOS one-click runner script
├── run.ps1                  # Windows PowerShell runner script
├── .gitignore               # Git exclude rules
└── README.md                # Project documentation
```

---

## 🚀 Quickstart Guide

### Prerequisites
- Python **3.11** or **3.12**
- Git

### 1. Clone & Set Up Environment
```bash
git clone https://github.com/Ayushman147/Smart-Home-Health-Monitoring-System.git
cd Smart-Home-Health-Monitoring-System

# Optional: Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Train the Synthetic ML Model
```bash
python ml/train.py
```
*Outputs model performance (AUROC ~0.99 on synthetic data) and exports `ml/model.pkl`.*

### 3. Launch WardZero Stack

**On Linux / macOS / Git Bash:**
```bash
chmod +x run.sh
./run.sh
```

**On Windows (PowerShell):**
```powershell
.\run.ps1
```

*Or run backend and simulator in separate terminals:*
```bash
# Terminal 1: Backend
uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Terminal 2: Simulator
python simulator/simulator.py
```

### 4. Open Dashboard
Open your web browser and navigate to:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 🧪 Running Automated Tests

WardZero includes an automated test suite verifying edge cases, deduplication, clinical scoring, and offline buffering:

```bash
python -m pytest tests/test_wardzero.py -v
```

### Test Coverage Highlights:
- `test_1_sequence_deduplication`: Validates `UNIQUE(device_id, sequence_num)` prevents replay duplicates.
- `test_2_data_quality_corrupt_detection`: Asserts flatline/impossible metrics flag as sensor defects rather than medical alarms.
- `test_3_rule_based_news2_inspired_score`: Validates hypoxia scoring adjusted for COPD target ranges.
- `test_4_caregiver_keywords_raise_risk`: Confirms natural language symptom keywords elevate priority.
- `test_5_alert_cooldown_and_escalation`: Verifies SLA timeout auto-escalates from Caregiver A &rarr; Caregiver B.
- `test_6_offline_store_and_forward_buffer`: Validates disconnected packets buffer locally without data loss.

---

## 🎬 3-Minute Demo Story

Follow this sequential scenario during live presentations:

1. **Baseline Stability**: Open dashboard for **Mr. Sharma (P001, 72, COPD)**. Observe normal telemetry (SpO2 ~95%, HR ~76 bpm) with a green `LOW RISK` badge.
2. **Contextual Keyword Trigger**: In the Caregiver Observation input, submit:
   ```
   Patient feels breathless and fatigued after walking to kitchen
   ```
   The engine extracts the keyword `"breathless"`, elevating risk to `WARNING` and documenting the finding in plain English.
3. **Escalation SLA**: Allow 30 seconds without acknowledging (or expand the **Failure Demonstration Panel** and toggle *"Caregiver Unresponsive"*). Watch the alert escalate from **Caregiver A &rarr; Caregiver B &rarr; Family &rarr; Medical Professional**, logged in real-time in the Notification Outbox.
4. **Network Cut & Recovery**: Click **"Cut Network"** in the failure sandbox. Telemetry disconnects and flags `Device Offline`. Meanwhile, the simulator buffers readings locally. Click **"Restore Network"** to see all queued packets back-fill chronologically.
5. **Caregiver Resolution**: Nurse clicks **"On My Way"** and **"Resolved"**. The active escalation clears, and baseline status resumes.

---

## 🛠️ Failure Demonstration Panel

Located at the bottom of the dashboard, this interactive evaluation tool enables live chaos-testing:

| Chaos Action | Underlying Mechanism | Observable Result |
| :--- | :--- | :--- |
| **Cut Network** | Server returns `503 Service Unavailable` on `/ingest` | Simulator stores packets in `buffer.json`; UI flags device offline; re-buffers drain upon restore |
| **Simulate Corrupt Data** | Telemetry packets inject impossible vitals (HR=0 or SpO2<40%) | Engine tags packet as `Sensor Transmission Issue` and avoids triggering code-blue panic alerts |
| **Caregiver Unresponsive** | Simulates expiration of caregiver response SLA timer | Alert cascades up the chain to secondary nurse, family contact, and emergency clinical contacts |

---

## 🔬 Clinical & ML Methodology

### 1. Hybrid Risk Fusion
Rather than relying solely on black-box predictions, WardZero couples a deterministic rule set with statistical forecasting:
- **NEWS2-Inspired Floor**: Detects acute boundary breaches with specific calibration for hypercapnic respiratory drive (COPD target 88–92%).
- **Scikit-Learn Logistic Regression**: Evaluates rolling window features ($\mu, \sigma, \Delta$) across 15 historical telemetry cycles to forecast 24–48h deterioration trajectory.

### 2. Linear Explainability ($\beta_i \cdot x_i$)
To satisfy home healthcare explainability needs without heavy dependencies (e.g., SHAP), individual risk drivers are computed directly:
$$\text{Contribution}_i = \beta_i \cdot z_i$$
where $\beta_i$ is the trained model coefficient and $z_i$ is the standardized feature value. The top positive contributors are converted into plain-English explanations.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
