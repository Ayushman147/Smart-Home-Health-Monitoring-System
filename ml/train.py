import csv
import pickle
import os
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
import numpy as np

def train_model():
    current_dir = os.path.dirname(__file__)
    data_file = os.path.join(current_dir, "synthetic_vitals.csv")
    
    if not os.path.exists(data_file):
        from generate_data import generate_synthetic_data
        generate_synthetic_data(filename=data_file)
        
    features = []
    labels = []
    feature_names = [
        "spo2_mean", "spo2_slope", "spo2_std",
        "hr_mean", "hr_slope", "hr_std",
        "sys_mean", "sys_slope",
        "has_symptom", "age", "is_copd"
    ]
    
    with open(data_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            features.append([float(row[k]) for k in feature_names])
            labels.append(int(row["deterioration_24_48h"]))
            
    X = np.array(features)
    y = np.array(labels)
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    clf = LogisticRegression(class_weight="balanced", random_state=42)
    clf.fit(X_train_scaled, y_train)
    
    y_pred_proba = clf.predict_proba(X_test_scaled)[:, 1]
    auroc = roc_auc_score(y_test, y_pred_proba)
    
    print("==================================================")
    print("WardZero Logistic Regression Model Training")
    print(f"AUROC: {auroc:.4f} (synthetic data)")
    print("Note: Synthetic data only. For decision support demo.")
    print("==================================================")
    
    model_bundle = {
        "model": clf,
        "scaler": scaler,
        "feature_names": feature_names,
        "auroc": auroc
    }
    
    model_path = os.path.join(current_dir, "model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model_bundle, f)
        
    print(f"Model saved to {model_path}")
    return auroc

if __name__ == "__main__":
    train_model()

