import time
import json
import random
import os
from datetime import datetime, timezone
import requests

API_URL = "http://127.0.0.1:8000/ingest"
BUFFER_FILE = os.path.join(os.path.dirname(__file__), "buffer.json")

class PatientSimulator:
    def __init__(self, patient_id, device_id, scenario="stable"):
        self.patient_id = patient_id
        self.device_id = device_id
        self.scenario = scenario  # "stable", "slow_deterioration", "sudden_spo2_drop"
        self.sequence_num = 0
        self.step_count = 0
        
        # Baselines
        if patient_id == "P001":  # Mr. Sharma (COPD)
            self.hr = 76.0
            self.spo2 = 95.0
            self.sys = 126.0
            self.dia = 80.0
            self.temp = 36.8
        else:                     # Mrs. Anita Rao
            self.hr = 72.0
            self.spo2 = 98.0
            self.sys = 118.0
            self.dia = 76.0
            self.temp = 36.6

    def generate_reading(self):
        self.sequence_num += 1
        self.step_count += 1
        
        # Scenario behavioral dynamics
        if self.scenario == "stable":
            self.hr += random.uniform(-0.5, 0.5)
            self.spo2 += random.uniform(-0.2, 0.2)
            self.sys += random.uniform(-0.8, 0.8)
            self.dia += random.uniform(-0.5, 0.5)
            self.temp += random.uniform(-0.02, 0.02)
            # Bound within normal healthy ranges
            self.spo2 = max(94.0, min(98.0, self.spo2))
            self.hr = max(68.0, min(80.0, self.hr))
            
        elif self.scenario == "slow_deterioration":
            # Compressed for demo: drops SpO2 and raises/lowers vitals progressively
            self.spo2 -= random.uniform(0.3, 0.6)
            self.hr += random.uniform(0.4, 0.9) # respiratory distress compensatory tachycardia
            self.sys += random.uniform(0.5, 1.2)
            self.temp += random.uniform(0.01, 0.05)
            self.spo2 = max(82.0, self.spo2)
            self.hr = min(118.0, self.hr)
            
        elif self.scenario == "sudden_spo2_drop":
            if self.step_count > 3:
                self.spo2 -= random.uniform(1.5, 3.0)
                self.spo2 = max(80.0, self.spo2)
                self.hr += random.uniform(1.0, 2.5)

        return {
            "device_id": self.device_id,
            "sequence_num": self.sequence_num,
            "patient_id": self.patient_id,
            "heart_rate": round(self.hr, 1),
            "spo2": round(self.spo2, 1),
            "bp_sys": round(self.sys, 1),
            "bp_dia": round(self.dia, 1),
            "temperature": round(self.temp, 1),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

def load_buffer():
    if os.path.exists(BUFFER_FILE):
        try:
            with open(BUFFER_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_buffer(buffer):
    with open(BUFFER_FILE, "w") as f:
        json.dump(buffer, f)

def send_or_buffer(reading, buffer):
    """
    Store-and-forward mechanism:
    Attempt sending current reading. If connection refused or 503 network cut,
    buffer it locally. When network is restored, replay all buffered readings in order.
    """
    headers = {"Content-Type": "application/json"}
    
    # 1. Attempt to flush buffer first if anything is queued
    if buffer:
        print(f"[*] Attempting to flush {len(buffer)} buffered readings...")
        flushed_indices = []
        for i, queued_item in enumerate(buffer):
            try:
                res = requests.post(API_URL, json=queued_item, timeout=2.0)
                if res.status_code == 200:
                    flushed_indices.append(i)
                else:
                    break
            except Exception:
                break
        
        # Remove successfully flushed items
        if flushed_indices:
            buffer = [item for idx, item in enumerate(buffer) if idx not in flushed_indices]
            save_buffer(buffer)
            print(f"[+] Successfully replayed {len(flushed_indices)} buffered readings!")

    # 2. Send current reading
    try:
        res = requests.post(API_URL, json=reading, headers=headers, timeout=2.0)
        if res.status_code == 200:
            print(f"[OK] Sent {reading['patient_id']} seq #{reading['sequence_num']} | SpO2: {reading['spo2']}% HR: {reading['heart_rate']} bpm")
            return buffer
        else:
            print(f"[!] Server returned {res.status_code}. Buffering reading #{reading['sequence_num']}...")
            buffer.append(reading)
            save_buffer(buffer)
            return buffer
    except Exception as e:
        print(f"[X] Backend unreachable ({e.__class__.__name__}). Storing seq #{reading['sequence_num']} in store-and-forward buffer.")
        buffer.append(reading)
        save_buffer(buffer)
        return buffer

def run_simulation(interval=2.0, iterations=None):
    print("=== WardZero Vital Sensors Simulator Started ===")
    print("Patients: P001 (Mr. Sharma - COPD), P002 (Mrs. Anita Rao)")
    
    sim_p1 = PatientSimulator("P001", "DEV-P001-A", scenario="stable")
    sim_p2 = PatientSimulator("P002", "DEV-P002-B", scenario="stable")
    
    buffer = load_buffer()
    count = 0
    
    try:
        while True:
            # Check backend toggles or scenarios if needed
            # Patient 1 reading
            r1 = sim_p1.generate_reading()
            buffer = send_or_buffer(r1, buffer)
            
            # Patient 2 reading
            r2 = sim_p2.generate_reading()
            buffer = send_or_buffer(r2, buffer)
            
            count += 1
            if iterations and count >= iterations:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nSimulator stopped by user.")

if __name__ == "__main__":
    run_simulation()

