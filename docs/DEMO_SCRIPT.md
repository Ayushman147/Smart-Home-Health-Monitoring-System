# WardZero: 3-Minute Hackathon Judge Demo Script

**Theme**: Smart Home Healthcare Monitoring (Decision Support)  
**Presenter**: WardZero Lead Developer  
**Target Time**: ~180 seconds  

---

### [00:00 - 00:30] Introduction & The Problem
> *"Good morning judges. Meet Mr. Sharma, a 72-year-old gentleman living at home with COPD. In traditional home care, physiological crises happen because subtle deteriorations over 24 to 48 hours are missed, and when an alarm finally rings, alert fatigue causes it to be ignored.*
>
> *This is **WardZero**: a lightweight, decision-support prototype built to catch early deterioration, explain its reasoning transparently, and escalate alerts reliably when caregivers don't respond."*

---

### [00:30 - 01:10] The Dashboard & Hybrid Risk Engine
> *"Looking at our screen at `http://localhost:8000`:
> - Notice our clean, minimal dashboard with zero build steps—running vanilla JS and Tailwind.
> - At the top, we see Mr. Sharma's 4 core vitals streaming every 2 seconds with live sparklines: SpO2, Heart Rate, Blood Pressure, and Temperature.
> - Beside the live trend chart, observe our **Hybrid Risk Assessment**. It's powered by a clinical safety floor inspired by NEWS2 combined with a lightweight Scikit-Learn Logistic Regression model predicting 24–48 hour deterioration risk.
> - Notice the **'Why?' section**: we don't just give an alert score; we calculate coefficient weights to explain in plain English why risk is elevated—without heavy black-box SHAP libraries."*

---

### [01:10 - 01:50] Real-world Context & Symptom Injection
> *"Now let's introduce real-world home care context. A visiting aide notes that Mr. Sharma is struggling to walk.
> Let's type in the Caregiver Note box: **'Patient feels breathless and fatigued after walking'** and hit Post.
>
> Look at the risk card instantly update:
> 1. The keyword **'breathless'** is extracted from the caregiver note.
> 2. The risk level rises to **WARNING / URGENT**.
> 3. The explanation specifically identifies that a caregiver symptom note matches a known deterioration pattern.
> 4. In the Caregiver Escalation box, an alert is dispatched to **Caregiver A**, with a simulated SMS sent to our Notification Outbox below."*

---

### [01:50 - 02:30] The Failure Demo: Escalation & Offline Store-and-Forward
> *"In real home deployments, things fail. Let's open our **Failure Demonstration Panel**:
>
> **1. Unresponsive Caregivers**:
> Suppose Caregiver A drops their phone or is unavailable. After 30 seconds (or clicking 'Caregiver Unresponsive'), watch the alert auto-escalate: Caregiver A &rarr; Caregiver B &rarr; Family Member &rarr; Emergency Medical Professional. You can see the simulated WhatsApp alert generated in our Outbox.
>
> **2. Offline Network Buffering**:
> Now let's hit **'Cut Network'**. The telemetry stream stops, and the top bar flags the device as offline. But our edge simulator doesn't drop a single packet—it buffers readings into a local store-and-forward queue.
>
> When we hit **'Restore Network'**, watch the simulator immediately flush the entire buffered sequence chronologically. The backend deduplicates without dropping data or crashing."*

---

### [02:30 - 03:00] Caregiver Resolution & Closing
> *"Now, Nurse Sarah arrives on scene. She clicks **'On My Way'** and then **'Resolved'** with the note 'Oxygen concentrator tubing cleared; patient resting comfortably.'
>
> The active alert dismisses, the risk resets to normal, and the audit trail is recorded.
>
> In under 1,500 lines of code across just 10 files, WardZero demonstrates end-to-end edge-to-cloud resilience, explainable ML decision support, and life-saving escalation for home healthcare.
>
> Thank you, and we're ready for your questions!"*

