import numpy as np
import csv
import random

def generate_synthetic_data(num_samples=2500, filename="synthetic_vitals.csv"):
    """
    Generate synthetic longitudinal rolling vital statistics for training
    logistic regression to predict 'risk of deterioration in next 24-48h'.
    Features:
    - spo2_mean, spo2_slope, spo2_std
    - hr_mean, hr_slope, hr_std
    - sys_mean, sys_slope
    - has_critical_symptoms (binary flag: breathless, dizzy, confused, etc.)
    - age
    - is_copd (binary flag)
    """
    np.random.seed(42)
    random.seed(42)
    
    rows = []
    for i in range(num_samples):
        # 30% positive deterioration cases
        deteriorates = 1 if np.random.rand() < 0.28 else 0
        
        is_copd = 1 if np.random.rand() < 0.35 else 0
        age = int(np.random.normal(68, 10))
        age = max(35, min(95, age))
        
        if deteriorates:
            # Deteriorating profile: falling SpO2 slope, rising or falling HR, erratic BP
            spo2_mean = np.random.normal(91.5 if is_copd else 93.0, 2.0)
            spo2_slope = np.random.normal(-0.6, 0.4) # dropping
            spo2_std = np.random.exponential(1.5) + 0.8
            
            hr_mean = np.random.normal(92, 12)
            hr_slope = np.random.normal(0.4, 0.5) # accelerating or erratic
            hr_std = np.random.exponential(3.0) + 1.5
            
            sys_mean = np.random.normal(138, 18)
            sys_slope = np.random.normal(0.3, 0.8)
            
            # Likely caregiver symptom note present
            has_symptom = 1 if np.random.rand() < 0.70 else 0
        else:
            # Stable profile
            spo2_mean = np.random.normal(94.5 if is_copd else 97.5, 1.2)
            spo2_slope = np.random.normal(0.0, 0.1) # flat/stable
            spo2_std = np.random.exponential(0.5) + 0.2
            
            hr_mean = np.random.normal(74, 8)
            hr_slope = np.random.normal(0.0, 0.2)
            hr_std = np.random.exponential(1.2) + 0.5
            
            sys_mean = np.random.normal(122, 10)
            sys_slope = np.random.normal(0.0, 0.3)
            
            has_symptom = 1 if np.random.rand() < 0.10 else 0
            
        rows.append({
            "spo2_mean": round(float(spo2_mean), 2),
            "spo2_slope": round(float(spo2_slope), 3),
            "spo2_std": round(float(spo2_std), 2),
            "hr_mean": round(float(hr_mean), 1),
            "hr_slope": round(float(hr_slope), 3),
            "hr_std": round(float(hr_std), 2),
            "sys_mean": round(float(sys_mean), 1),
            "sys_slope": round(float(sys_slope), 3),
            "has_symptom": has_symptom,
            "age": age,
            "is_copd": is_copd,
            "deterioration_24_48h": deteriorates
        })
        
    keys = rows[0].keys()
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {num_samples} synthetic samples in {filename}")

if __name__ == "__main__":
    generate_synthetic_data()
