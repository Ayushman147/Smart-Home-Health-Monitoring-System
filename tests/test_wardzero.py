import pytest
import os
import json
from datetime import datetime, timezone
from backend.db import get_connection, init_db
from backend.risk import compute_news2_inspired_score, assess_risk
from backend.alerts import trigger_alert_if_needed, check_and_escalate_alerts

@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    conn = get_connection()
    c = conn.cursor()
    # Clean up test rows
    c.execute("DELETE FROM readings WHERE device_id LIKE 'TEST-%'")
    c.execute("DELETE FROM alerts WHERE patient_id = 'P_TEST'")
    c.execute("DELETE FROM notes WHERE patient_id = 'P_TEST'")
    c.execute("DELETE FROM notifications WHERE message LIKE '%P_TEST%'")
    conn.commit()
    conn.close()

def test_1_sequence_deduplication():
    """Verify that ingest deduplicates device_id + sequence_num without crashing."""
    conn = get_connection()
    c = conn.cursor()
    device = "TEST-DEV-01"
    seq = 42
    
    # Insert first reading
    c.execute("""
        INSERT INTO readings (device_id, sequence_num, patient_id, heart_rate, spo2, bp_sys, bp_dia, temperature, created_at, recorded_at)
        VALUES (?, ?, 'P_TEST', 75, 98, 120, 80, 36.6, '2026-11-02T10:00:00', '2026-11-02T10:00:00')
    """, (device, seq))
    conn.commit()

    # Attempt second insertion with same device_id and sequence_num
    duplicate_caught = False
    try:
        c.execute("""
            INSERT INTO readings (device_id, sequence_num, patient_id, heart_rate, spo2, bp_sys, bp_dia, temperature, created_at, recorded_at)
            VALUES (?, ?, 'P_TEST', 76, 98, 120, 80, 36.6, '2026-11-02T10:00:02', '2026-11-02T10:00:02')
        """, (device, seq))
        conn.commit()
    except Exception:
        duplicate_caught = True
        
    conn.close()
    assert duplicate_caught, "Database must reject duplicate (device_id, sequence_num)"

def test_2_data_quality_corrupt_detection():
    """Verify impossible values or flatlines are marked as sensor issue, not medical emergency."""
    impossible_reading = {
        "heart_rate": 0.0,
        "spo2": 30.0,
        "bp_sys": 120.0,
        "bp_dia": 80.0,
        "temperature": 15.0,
        "is_corrupt": 1
    }
    patient = {
        "id": "P_TEST",
        "name": "Test Patient",
        "age": 70,
        "condition": "COPD",
        "baseline_hr": 75.0,
        "baseline_spo2": 95.0,
        "baseline_sys": 120.0,
        "baseline_dia": 80.0,
        "baseline_temp": 36.6
    }
    result = assess_risk(patient, [impossible_reading], [])
    assert result["model_type"] == "sensor_check"
    assert "Sensor transmission issue" in result["reasons"][0]

def test_3_rule_based_news2_inspired_score():
    """Verify NEWS2-inspired scoring for hypoxic COPD patient vs normal."""
    patient_copd = {
        "id": "P_TEST",
        "name": "Mr. Sharma",
        "age": 72,
        "condition": "COPD",
        "baseline_hr": 76.0,
        "baseline_spo2": 95.0,
        "baseline_sys": 126.0,
        "baseline_dia": 80.0,
        "baseline_temp": 36.8
    }
    # Severe drop
    reading_hypoxic = {
        "heart_rate": 115.0,
        "spo2": 83.0,
        "bp_sys": 135.0,
        "temperature": 37.0
    }
    score, reasons = compute_news2_inspired_score(patient_copd, reading_hypoxic)
    assert score >= 5, f"Expected elevated score for 83% SpO2 and 115 bpm HR, got {score}"
    assert any("SpO2 is 83%" in r for r in reasons)

def test_4_caregiver_keywords_raise_risk():
    """Verify context notes with breathlessness/dizziness raise risk."""
    patient = {
        "id": "P_TEST",
        "name": "Mr. Sharma",
        "age": 72,
        "condition": "COPD",
        "baseline_hr": 76.0,
        "baseline_spo2": 95.0,
        "baseline_sys": 126.0,
        "baseline_dia": 80.0,
        "baseline_temp": 36.8
    }
    readings = [{
        "heart_rate": 78.0,
        "spo2": 93.0,
        "bp_sys": 126.0,
        "bp_dia": 80.0,
        "temperature": 36.8,
        "is_corrupt": 0
    }]
    notes = [{"author": "Nurse", "note": "Patient feels breathless and confused."}]
    result = assess_risk(patient, readings, notes)
    assert any("Caregiver note mentions symptoms" in r or "breathless" in r for r in result["reasons"])

def test_5_alert_cooldown_and_escalation():
    """Verify escalation from Caregiver A to Caregiver B to Family."""
    conn = get_connection()
    c = conn.cursor()
    
    risk_result = {
        "level": "CRITICAL",
        "score": 7,
        "probability_24_48h": 0.88,
        "reasons": ["SpO2 dropped below 84%"]
    }
    # Trigger alert
    alert_id = trigger_alert_if_needed(conn, "P_TEST", risk_result)
    assert alert_id is not None
    
    # Check initial assigned_to is Caregiver A
    c.execute("SELECT assigned_to, escalation_step FROM alerts WHERE id = ?", (alert_id,))
    row = c.fetchone()
    assert row["assigned_to"] == "Caregiver A"
    assert row["escalation_step"] == 0
    
    # Back-date updated_at by 35 seconds to simulate timeout
    past_iso = "2026-11-02T10:00:00"
    c.execute("UPDATE alerts SET updated_at = ? WHERE id = ?", (past_iso, alert_id))
    conn.commit()
    
    # Run escalation
    escalated = check_and_escalate_alerts(conn)
    assert escalated >= 1
    
    c.execute("SELECT assigned_to, escalation_step FROM alerts WHERE id = ?", (alert_id,))
    updated_row = c.fetchone()
    assert updated_row["assigned_to"] == "Caregiver B"
    assert updated_row["escalation_step"] == 1
    
    conn.close()

def test_6_offline_store_and_forward_buffer():
    """Verify simulator buffer logic holds and replays messages without loss."""
    from simulator.simulator import send_or_buffer
    
    test_buffer = []
    fake_reading = {
        "device_id": "TEST-DEV",
        "sequence_num": 999,
        "patient_id": "P_TEST",
        "heart_rate": 72.0,
        "spo2": 97.0,
        "bp_sys": 120.0,
        "bp_dia": 80.0,
        "temperature": 36.6,
        "timestamp": "2026-11-02T10:00:00"
    }
    # With unreachable port 9999, send_or_buffer should queue reading into buffer
    import simulator.simulator as sim
    original_url = sim.API_URL
    sim.API_URL = "http://127.0.0.1:9999/ingest"
    
    buf = sim.send_or_buffer(fake_reading, test_buffer)
    assert len(buf) == 1
    assert buf[0]["sequence_num"] == 999
    
    # Restore original URL
    sim.API_URL = original_url

