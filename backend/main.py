import os
import sys
import json
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

from db import get_connection, init_db
from risk import assess_risk
from alerts import trigger_alert_if_needed, check_and_escalate_alerts

app = FastAPI(title="WardZero - Smart Home Healthcare Monitoring")

# Ensure database tables exist
init_db()

# --- Pydantic Request Models ---
class IngestReading(BaseModel):
    device_id: str
    sequence_num: int
    patient_id: str
    heart_rate: float
    spo2: float
    bp_sys: float
    bp_dia: float
    temperature: float
    timestamp: str  # Original recording timestamp (supports late/replay)

class AcknowledgeRequest(BaseModel):
    alert_id: int
    status: str       # 'Acknowledged', 'OnMyWay', 'Resolved'
    caregiver: str
    note: Optional[str] = None

class CaregiverNoteRequest(BaseModel):
    patient_id: str
    author: str
    note: str

class ToggleRequest(BaseModel):
    key: str          # 'network_cut', 'simulate_unresponsive', 'force_corrupt'
    value: str        # 'true' or 'false'

# --- 1. Ingestion Endpoint ---
@app.post("/ingest")
def ingest_reading(reading: IngestReading):
    conn = get_connection()
    c = conn.cursor()

    # Check failure toggle: if network is cut, reject to simulate dropped connection
    c.execute("SELECT value FROM system_state WHERE key = 'network_cut'")
    row = c.fetchone()
    if row and row["value"] == "true":
        conn.close()
        raise HTTPException(status_code=503, detail="Simulated Network Outage: Ingestion endpoint offline")

    # Check failure toggle: force corrupt data
    c.execute("SELECT value FROM system_state WHERE key = 'force_corrupt'")
    fc_row = c.fetchone()
    force_corrupt = (fc_row and fc_row["value"] == "true")

    # Data Quality & Sanity checks
    is_corrupt = 0
    quality_issue = None
    
    # Flatline, impossible or out-of-range sensor values
    if force_corrupt or reading.heart_rate <= 0 or reading.heart_rate > 260 or \
       reading.spo2 <= 40 or reading.spo2 > 100 or reading.temperature < 25 or reading.temperature > 46:
        is_corrupt = 1
        quality_issue = "Sensor transmission issue / impossible sensor reading detected (not patient emergency)"

    now_server_str = datetime.now(timezone.utc).isoformat()

    try:
        c.execute("""
            INSERT INTO readings 
            (device_id, sequence_num, patient_id, heart_rate, spo2, bp_sys, bp_dia, temperature, is_corrupt, data_quality_issue, created_at, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            reading.device_id,
            reading.sequence_num,
            reading.patient_id,
            reading.heart_rate,
            reading.spo2,
            reading.bp_sys,
            reading.bp_dia,
            reading.temperature,
            is_corrupt,
            quality_issue,
            now_server_str,
            reading.timestamp
        ))
        conn.commit()
    except Exception as e:
        # Deduplication match on UNIQUE(device_id, sequence_num)
        conn.close()
        return {"status": "deduplicated", "detail": f"Reading #{reading.sequence_num} already processed"}

    # Automatic risk check and alert trigger on fresh non-corrupt reading
    if not is_corrupt:
        c.execute("SELECT * FROM patients WHERE id = ?", (reading.patient_id,))
        patient = c.fetchone()
        if patient:
            # Get last 20 readings for rolling window
            c.execute("SELECT * FROM readings WHERE patient_id = ? ORDER BY recorded_at ASC LIMIT 30", (reading.patient_id,))
            history = [dict(r) for r in c.fetchall()]
            
            c.execute("SELECT * FROM notes WHERE patient_id = ? ORDER BY id DESC LIMIT 5", (reading.patient_id,))
            notes = [dict(n) for n in c.fetchall()]
            
            risk_result = assess_risk(dict(patient), history, notes)
            trigger_alert_if_needed(conn, reading.patient_id, risk_result)

    conn.close()
    return {"status": "success", "sequence_num": reading.sequence_num, "corrupt_flagged": is_corrupt}

# --- 2. Query Endpoints ---
@app.get("/patients")
def get_patients():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM patients")
    patients = [dict(r) for r in c.fetchall()]
    
    # Check device online / offline status (no data received in > 15 seconds)
    now_ts = datetime.now(timezone.utc).timestamp()
    results = []
    for p in patients:
        c.execute("SELECT recorded_at, created_at FROM readings WHERE patient_id = ? ORDER BY id DESC LIMIT 1", (p["id"],))
        last_reading = c.fetchone()
        
        is_online = False
        last_seen_sec = 9999
        if last_reading:
            last_dt = datetime.fromisoformat(last_reading["created_at"]).timestamp()
            last_seen_sec = round(now_ts - last_dt, 1)
            is_online = (last_seen_sec <= 15)
            
        p_dict = dict(p)
        p_dict["is_online"] = is_online
        p_dict["last_seen_seconds_ago"] = last_seen_sec
        results.append(p_dict)

    conn.close()
    return results

@app.get("/vitals/{patient_id}")
def get_vitals(patient_id: str, limit: int = 30):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM readings 
        WHERE patient_id = ? 
        ORDER BY id DESC LIMIT ?
    """, (patient_id, limit))
    readings = [dict(r) for r in c.fetchall()]
    conn.close()
    return list(reversed(readings))

@app.get("/risk/{patient_id}")
def get_patient_risk(patient_id: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
    patient = c.fetchone()
    if not patient:
        conn.close()
        raise HTTPException(status_code=404, detail="Patient not found")
        
    c.execute("SELECT * FROM readings WHERE patient_id = ? ORDER BY recorded_at ASC LIMIT 30", (patient_id,))
    history = [dict(r) for r in c.fetchall()]
    
    c.execute("SELECT * FROM notes WHERE patient_id = ? ORDER BY id DESC LIMIT 5", (patient_id,))
    notes = [dict(n) for n in c.fetchall()]
    
    # Run escalation cycle
    check_and_escalate_alerts(conn)
    
    risk_result = assess_risk(dict(patient), history, notes)
    conn.close()
    return risk_result

@app.get("/alerts")
def get_alerts(patient_id: Optional[str] = None):
    conn = get_connection()
    c = conn.cursor()
    check_and_escalate_alerts(conn)
    
    if patient_id:
        c.execute("SELECT * FROM alerts WHERE patient_id = ? ORDER BY id DESC LIMIT 20", (patient_id,))
    else:
        c.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 25")
    
    alerts = []
    for r in c.fetchall():
        d = dict(r)
        try:
            d["reasons"] = json.loads(d["reasons"])
        except Exception:
            d["reasons"] = [d["reasons"]]
        alerts.append(d)
        
    conn.close()
    return alerts

@app.post("/acknowledge")
def acknowledge_alert(req: AcknowledgeRequest):
    conn = get_connection()
    c = conn.cursor()
    now_str = datetime.now(timezone.utc).isoformat()
    
    c.execute("""
        UPDATE alerts 
        SET status = ?, acknowledged_by = ?, updated_at = ?
        WHERE id = ?
    """, (req.status, req.caregiver, now_str, req.alert_id))
    
    if req.note:
        c.execute("SELECT patient_id FROM alerts WHERE id = ?", (req.alert_id,))
        patient = c.fetchone()
        if patient:
            c.execute("""
                INSERT INTO notes (patient_id, author, note, created_at)
                VALUES (?, ?, ?, ?)
            """, (patient["patient_id"], req.caregiver, req.note, now_str))
            
    conn.commit()
    conn.close()
    return {"status": "success", "alert_id": req.alert_id, "new_status": req.status}

@app.get("/notes/{patient_id}")
def get_notes(patient_id: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM notes WHERE patient_id = ? ORDER BY id DESC LIMIT 15", (patient_id,))
    notes = [dict(r) for r in c.fetchall()]
    conn.close()
    return notes

@app.post("/notes")
def add_note(req: CaregiverNoteRequest):
    conn = get_connection()
    c = conn.cursor()
    now_str = datetime.now(timezone.utc).isoformat()
    c.execute("""
        INSERT INTO notes (patient_id, author, note, created_at)
        VALUES (?, ?, ?, ?)
    """, (req.patient_id, req.author, req.note, now_str))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/notifications")
def get_notifications():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT 15")
    items = [dict(r) for r in c.fetchall()]
    conn.close()
    return items

@app.get("/state")
def get_state():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT key, value FROM system_state")
    state = {r["key"]: r["value"] for r in c.fetchall()}
    conn.close()
    return state

@app.post("/failure-toggle")
def failure_toggle(req: ToggleRequest):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO system_state (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (req.key, req.value))
    conn.commit()
    conn.close()
    return {"status": "success", "key": req.key, "value": req.value}

# --- 3. Frontend Static Serving ---
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(FRONTEND_DIR):
    @app.get("/", response_class=HTMLResponse)
    def serve_frontend():
        index_file = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                return f.read()
        return "<h3>WardZero Frontend Loading...</h3>"

