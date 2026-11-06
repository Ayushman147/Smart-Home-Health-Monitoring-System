import os
import pickle
import numpy as np

# Load trained logistic regression model if available
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ml", "model.pkl")

def get_ml_model():
    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None

def compute_news2_inspired_score(patient, latest_reading):
    """
    Rule-based score inspired by NEWS2 (National Early Warning Score 2).
    LABEL: 'Inspired by NEWS2, not clinically validated. Synthetic decision support only.'
    Returns: score (int), component_reasons (list[str])
    """
    score = 0
    reasons = []
    
    spo2 = latest_reading["spo2"]
    hr = latest_reading["heart_rate"]
    sys = latest_reading["bp_sys"]
    temp = latest_reading["temperature"]
    condition = patient["condition"].upper() if "condition" in patient else ""
    is_copd = "COPD" in condition

    # SpO2 scoring (adjust threshold scale for COPD if target 88-92%)
    if is_copd:
        if spo2 <= 83:
            score += 3
            reasons.append(f"SpO2 is {spo2:.0f}%, critically low for hypercapnic/COPD status")
        elif spo2 in (84, 85):
            score += 2
            reasons.append(f"SpO2 is {spo2:.0f}%, markedly below target range")
        elif spo2 in (86, 87):
            score += 1
            reasons.append(f"SpO2 is {spo2:.0f}%, slightly low for COPD baseline")
        elif spo2 >= 97:
            score += 2  # Risk of hypercapnia on high O2
            reasons.append(f"SpO2 is {spo2:.0f}%, elevated for COPD patient (hypercapnia concern)")
    else:
        if spo2 <= 91:
            score += 3
            reasons.append(f"SpO2 is {spo2:.0f}%, severe hypoxia risk")
        elif spo2 in (92, 93):
            score += 2
            reasons.append(f"SpO2 is {spo2:.0f}%, below standard baseline")
        elif spo2 in (94, 95):
            score += 1
            reasons.append(f"SpO2 is {spo2:.0f}%, mildly depressed")

    # Heart Rate scoring
    if hr <= 40 or hr >= 131:
        score += 3
        reasons.append(f"Heart rate is {hr:.0f} bpm, marked bradycardia/tachycardia")
    elif hr >= 111 and hr <= 130:
        score += 2
        reasons.append(f"Heart rate is {hr:.0f} bpm, elevated tachycardia")
    elif (hr >= 41 and hr <= 50) or (hr >= 91 and hr <= 110):
        score += 1
        reasons.append(f"Heart rate is {hr:.0f} bpm, borderline normal")

    # Systolic BP scoring
    if sys <= 90 or sys >= 220:
        score += 3
        reasons.append(f"Systolic BP is {sys:.0f} mmHg, severe deviation")
    elif (sys >= 91 and sys <= 100) or (sys >= 180 and sys <= 219):
        score += 2
        reasons.append(f"Systolic BP is {sys:.0f} mmHg, moderate deviation")
    elif (sys >= 101 and sys <= 110) or (sys >= 160 and sys <= 179):
        score += 1
        reasons.append(f"Systolic BP is {sys:.0f} mmHg, mild deviation")

    # Temperature scoring
    if temp <= 35.0:
        score += 3
        reasons.append(f"Body temperature is {temp:.1f}°C, hypothermia risk")
    elif temp >= 39.1:
        score += 2
        reasons.append(f"Body temperature is {temp:.1f}°C, high fever")
    elif (temp >= 35.1 and temp <= 36.0) or (temp >= 38.1 and temp <= 39.0):
        score += 1
        reasons.append(f"Body temperature is {temp:.1f}°C, borderline abnormal")

    return score, reasons

def extract_caregiver_keywords(notes_list):
    """Detect keywords: breathless, dizzy, confused, not eating in recent notes."""
    keywords = ["breathless", "breathing", "dizzy", "confused", "not eating", "drowsy", "chest pain"]
    found = []
    for n in notes_list:
        text = n["note"].lower()
        for kw in keywords:
            if kw in text and kw not in found:
                found.append(kw)
    return found

def assess_risk(patient, readings_history, recent_notes=None):
    """
    Hybrid risk assessment:
    1. Rule-based NEWS2-inspired scoring -> LOW / MODERATE / HIGH / CRITICAL
    2. ML Logistic Regression for 'risk of deterioration in next 24-48h'
    3. Context enhancement (patient condition, baselines, caregiver notes)
    4. Top 3 plain English non-diagnostic reasons
    5. Degraded mode fallback if ML unavailable
    """
    if not readings_history:
        return {
            "level": "LOW",
            "score": 0,
            "probability_24_48h": 0.05,
            "reasons": ["No historical readings available yet; baseline normal."],
            "is_degraded": False,
            "model_type": "hybrid",
            "disclaimer": "Decision-support prototype. Synthetic data. Not a medical diagnosis."
        }
    
    valid_readings = [r for r in readings_history if not r.get("is_corrupt", 0)]
    if not valid_readings:
        return {
            "level": "WARNING",
            "score": 2,
            "probability_24_48h": 0.1,
            "reasons": ["Sensor transmission issues detected. Data corrupted or flatline."],
            "is_degraded": False,
            "model_type": "sensor_check",
            "disclaimer": "Decision-support prototype. Not a medical diagnosis."
        }

    latest = valid_readings[-1]
    rule_score, rule_reasons = compute_news2_inspired_score(patient, latest)
    
    # Caregiver note keywords
    if recent_notes is None:
        recent_notes = []
    symptom_kws = extract_caregiver_keywords(recent_notes)
    
    # Baseline comparison reasons
    spo2_drop = patient["baseline_spo2"] - latest["spo2"]
    if spo2_drop >= 3.0:
        rule_reasons.insert(0, f"SpO2 fell {spo2_drop:.1f} pts below patient baseline ({patient['baseline_spo2']}%)")
        rule_score += 2

    if symptom_kws:
        rule_reasons.insert(0, f"Caregiver note mentions symptoms ({', '.join(symptom_kws)})")
        rule_score += 2

    # Map rule score to Level
    if rule_score >= 7:
        rule_level = "CRITICAL"
    elif rule_score >= 5:
        rule_level = "HIGH"
    elif rule_score >= 3:
        rule_level = "MODERATE"
    else:
        rule_level = "LOW"

    # ML Assessment with Logistic Regression
    bundle = get_ml_model()
    is_degraded = (bundle is None)
    
    if not is_degraded:
        try:
            clf = bundle["model"]
            scaler = bundle["scaler"]
            
            # Compute rolling features over available window (up to last 15 readings)
            window = valid_readings[-15:]
            spo2_arr = np.array([r["spo2"] for r in window])
            hr_arr = np.array([r["heart_rate"] for r in window])
            sys_arr = np.array([r["bp_sys"] for r in window])
            
            spo2_mean = float(np.mean(spo2_arr))
            spo2_std = float(np.std(spo2_arr)) if len(spo2_arr) > 1 else 0.0
            spo2_slope = float((spo2_arr[-1] - spo2_arr[0]) / max(len(spo2_arr) - 1, 1))
            
            hr_mean = float(np.mean(hr_arr))
            hr_std = float(np.std(hr_arr)) if len(hr_arr) > 1 else 0.0
            hr_slope = float((hr_arr[-1] - hr_arr[0]) / max(len(hr_arr) - 1, 1))
            
            sys_mean = float(np.mean(sys_arr))
            sys_slope = float((sys_arr[-1] - sys_arr[0]) / max(len(sys_arr) - 1, 1))
            
            has_symptom = 1 if len(symptom_kws) > 0 else 0
            is_copd = 1 if "COPD" in patient["condition"].upper() else 0
            age = float(patient["age"])
            
            feat_vector = np.array([[
                spo2_mean, spo2_slope, spo2_std,
                hr_mean, hr_slope, hr_std,
                sys_mean, sys_slope,
                has_symptom, age, is_copd
            ]])
            
            scaled_feat = scaler.transform(feat_vector)
            prob_deterioration = float(clf.predict_proba(scaled_feat)[0, 1])
            
            # Explainability using coefficient * feature value (no SHAP needed!)
            coefs = clf.coef_[0]
            contributions = coefs * scaled_feat[0]
            feature_names = bundle["feature_names"]
            
            # Find top positive risk drivers
            top_indices = np.argsort(contributions)[::-1]
            ml_explanations = []
            for idx in top_indices:
                if contributions[idx] > 0.05:
                    fname = feature_names[idx]
                    if fname == "spo2_slope" and spo2_slope < 0:
                        ml_explanations.append(f"SpO2 has a downward trajectory of {spo2_slope:.2f}%/cycle")
                    elif fname == "spo2_mean" and spo2_mean < patient["baseline_spo2"]:
                        ml_explanations.append(f"Rolling mean SpO2 ({spo2_mean:.1f}%) is trending below baseline")
                    elif fname == "has_symptom" and has_symptom:
                        ml_explanations.append(f"Recorded notes reflect high-risk symptom keywords: {', '.join(symptom_kws)}")
                    elif fname == "hr_slope" and abs(hr_slope) > 0.2:
                        ml_explanations.append(f"Heart rate slope indicates physiological fluctuation ({hr_slope:+.2f} bpm/cycle)")
                    elif fname == "is_copd" and is_copd:
                        ml_explanations.append("Patient has preexisting COPD respiratory risk profile")
            
            # Combine explanations (prioritize concrete clinical & symptom reasons)
            combined_reasons = []
            for r in rule_reasons + ml_explanations:
                if r not in combined_reasons:
                    combined_reasons.append(r)
            
            # Reconcile risk level between rules and ML probability
            if prob_deterioration >= 0.75 or rule_level == "CRITICAL":
                final_level = "CRITICAL"
            elif prob_deterioration >= 0.50 or rule_level == "HIGH":
                final_level = "HIGH"
            elif prob_deterioration >= 0.30 or rule_level == "MODERATE":
                final_level = "MODERATE"
            else:
                final_level = "LOW"
                
            return {
                "level": final_level,
                "score": rule_score,
                "probability_24_48h": round(prob_deterioration, 3),
                "reasons": combined_reasons[:3] if combined_reasons else ["Vitals in range of baseline; normal stability."],
                "is_degraded": False,
                "model_type": "hybrid_logreg",
                "disclaimer": "Decision-support prototype (inspired by NEWS2, scikit-learn). Synthetic data. Not a medical diagnosis."
            }
        except Exception as e:
            is_degraded = True

    # Fallback / Degraded Mode (Rules only)
    prob_fallback = 0.85 if rule_level == "CRITICAL" else (0.60 if rule_level == "HIGH" else (0.35 if rule_level == "MODERATE" else 0.08))
    fallback_reasons = rule_reasons[:3] if rule_reasons else ["Vitals in range of baseline; normal stability."]
    fallback_reasons.append("ML model unavailable; operating in rule-based fallback mode.")
    
    return {
        "level": rule_level,
        "score": rule_score,
        "probability_24_48h": prob_fallback,
        "reasons": fallback_reasons[:3],
        "is_degraded": True,
        "model_type": "rule_based_fallback",
        "disclaimer": "Degraded mode active: rule-based only. Decision-support prototype. Not a medical diagnosis."
    }

