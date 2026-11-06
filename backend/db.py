import sqlite3
import os
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(__file__), "wardzero.db")

def get_connection():
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Patients table
    c.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        age INTEGER NOT NULL,
        condition TEXT NOT NULL,
        baseline_hr REAL NOT NULL,
        baseline_spo2 REAL NOT NULL,
        baseline_sys REAL NOT NULL,
        baseline_dia REAL NOT NULL,
        baseline_temp REAL NOT NULL
    )
    """)
    
    # Readings table (with sequence deduplication index)
    c.execute("""
    CREATE TABLE IF NOT EXISTS readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT NOT NULL,
        sequence_num INTEGER NOT NULL,
        patient_id TEXT NOT NULL,
        heart_rate REAL NOT NULL,
        spo2 REAL NOT NULL,
        bp_sys REAL NOT NULL,
        bp_dia REAL NOT NULL,
        temperature REAL NOT NULL,
        is_corrupt INTEGER DEFAULT 0,
        data_quality_issue TEXT,
        created_at TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        UNIQUE(device_id, sequence_num)
    )
    """)
    
    # Caregiver notes table
    c.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT NOT NULL,
        author TEXT NOT NULL,
        note TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    
    # Alerts table
    c.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT NOT NULL,
        level TEXT NOT NULL,          -- Info, Warning, Urgent, Critical
        message TEXT NOT NULL,
        reasons TEXT NOT NULL,        -- JSON or pipe-separated plain English reasons
        status TEXT NOT NULL,         -- Active, Acknowledged, OnMyWay, Resolved
        acknowledged_by TEXT,
        escalation_step INTEGER DEFAULT 0, -- 0: Caregiver A, 1: Caregiver B, 2: Family, 3: Medical Pro
        assigned_to TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    # Simulated Notification Outbox (SMS / WhatsApp logs)
    c.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient TEXT NOT NULL,
        channel TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # System Demo Toggles / Failure States
    c.execute("""
    CREATE TABLE IF NOT EXISTS system_state (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)
    
    # Seed default patients if not exist
    c.execute("SELECT COUNT(*) FROM patients")
    if c.fetchone()[0] == 0:
        c.execute("""
        INSERT INTO patients (id, name, age, condition, baseline_hr, baseline_spo2, baseline_sys, baseline_dia, baseline_temp)
        VALUES 
        ('P001', 'Mr. Sharma', 72, 'COPD', 76.0, 95.0, 126.0, 80.0, 36.8),
        ('P002', 'Mrs. Anita Rao', 68, 'Post-op Recovery', 72.0, 98.0, 118.0, 76.0, 36.6)
        """)

    # Initialize toggles
    toggles = {
        "network_cut": "false",
        "simulate_unresponsive": "false",
        "force_corrupt": "false"
    }
    for k, v in toggles.items():
        c.execute("INSERT OR IGNORE INTO system_state (key, value) VALUES (?, ?)", (k, v))
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")

