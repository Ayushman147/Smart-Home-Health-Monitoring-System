from datetime import datetime, timezone
import json

ESCALATION_CHAIN = [
    {"role": "Caregiver A", "contact": "A Nurse (Primary Mobile)"},
    {"role": "Caregiver B", "contact": "B Nurse (Secondary Mobile)"},
    {"role": "Family", "contact": "Next of Kin / Daughter"},
    {"role": "Medical Professional", "contact": "Emergency EMS / On-call Physician"}
]

ESCALATION_TIMEOUT_SECONDS = 30  # Demo time: 30s escalation
COOLDOWN_SECONDS = 20           # Deduplication cooldown per patient

def trigger_alert_if_needed(conn, patient_id, risk_result):
    """
    Evaluates current risk and checks whether a new alert should be raised,
    or if cooldown / deduplication suppresses it.
    Alert levels: Info, Warning, Urgent, Critical
    """
    level_map = {
        "LOW": "Info",
        "MODERATE": "Warning",
        "HIGH": "Urgent",
        "CRITICAL": "Critical"
    }
    target_alert_level = level_map.get(risk_result["level"], "Info")
    
    # If LOW, no active alarm needed unless resolving
    if target_alert_level == "Info":
        return None

    c = conn.cursor()
    now_str = datetime.now(timezone.utc).isoformat()
    now_ts = datetime.now(timezone.utc).timestamp()

    # Check for active unresolved alerts for this patient
    c.execute("""
        SELECT id, level, status, created_at, updated_at, escalation_step, assigned_to
        FROM alerts
        WHERE patient_id = ? AND status IN ('Active', 'OnMyWay')
        ORDER BY id DESC LIMIT 1
    """, (patient_id,))
    active_alert = c.fetchone()

    if active_alert:
        # Check cooldown or level upgrade
        created_time = datetime.fromisoformat(active_alert["created_at"]).timestamp()
        if (now_ts - created_time) < COOLDOWN_SECONDS and active_alert["level"] == target_alert_level:
            # Suppress alert fatigue within cooldown
            return None
        
        # If level intensified, escalate/update
        if target_alert_level in ("Urgent", "Critical") and active_alert["level"] == "Warning":
            reasons_json = json.dumps(risk_result["reasons"])
            c.execute("""
                UPDATE alerts
                SET level = ?, message = ?, reasons = ?, updated_at = ?
                WHERE id = ?
            """, (
                target_alert_level,
                f"Escalated condition detected. Recommend checking on patient.",
                reasons_json,
                now_str,
                active_alert["id"]
            ))
            conn.commit()
            return active_alert["id"]
        return None

    # Create brand new alert
    assigned_target = ESCALATION_CHAIN[0]["role"]
    reasons_json = json.dumps(risk_result["reasons"])
    msg = f"Elevated physiological risk level: {target_alert_level}. Recommend checking on patient."
    
    c.execute("""
        INSERT INTO alerts (patient_id, level, message, reasons, status, escalation_step, assigned_to, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'Active', 0, ?, ?, ?)
    """, (patient_id, target_alert_level, msg, reasons_json, assigned_target, now_str, now_str))
    alert_id = c.lastrowid

    # Post to simulated Notification Outbox (mock SMS/WhatsApp)
    outbox_msg = f"[{target_alert_level}] Alert for {patient_id}: {risk_result['reasons'][0] if risk_result['reasons'] else 'Vitals check needed'}"
    c.execute("""
        INSERT INTO notifications (recipient, channel, message, created_at)
        VALUES (?, 'SMS', ?, ?)
    """, (ESCALATION_CHAIN[0]["contact"], outbox_msg, now_str))
    
    conn.commit()
    return alert_id

def check_and_escalate_alerts(conn):
    """
    Checks all active unacknowledged alerts.
    If no acknowledgement within 30s (or failure simulation flag is set),
    escalate to next step in chain.
    """
    c = conn.cursor()
    now_ts = datetime.now(timezone.utc).timestamp()
    now_str = datetime.now(timezone.utc).isoformat()
    
    # Check if simulate_unresponsive toggle is active
    c.execute("SELECT value FROM system_state WHERE key = 'simulate_unresponsive'")
    sim_row = c.fetchone()
    force_escalate = (sim_row and sim_row["value"] == "true")

    c.execute("""
        SELECT id, patient_id, level, escalation_step, assigned_to, updated_at
        FROM alerts
        WHERE status = 'Active'
    """)
    active_alerts = c.fetchall()
    
    escalated_count = 0
    for a in active_alerts:
        updated_ts = datetime.fromisoformat(a["updated_at"]).timestamp()
        elapsed = now_ts - updated_ts
        
        if elapsed >= ESCALATION_TIMEOUT_SECONDS or force_escalate:
            curr_step = a["escalation_step"]
            next_step = curr_step + 1
            if next_step < len(ESCALATION_CHAIN):
                new_assignee = ESCALATION_CHAIN[next_step]["role"]
                new_contact = ESCALATION_CHAIN[next_step]["contact"]
                
                notice_msg = (
                    f"ESCALATION LEVEL {next_step}: Previous caregiver unresponsive. "
                    f"Alert for {a['patient_id']} assigned to {new_assignee} ({new_contact})."
                )
                if next_step == 3:
                    notice_msg += " Recommend contacting a medical professional immediately."

                c.execute("""
                    UPDATE alerts
                    SET escalation_step = ?, assigned_to = ?, updated_at = ?
                    WHERE id = ?
                """, (next_step, new_assignee, now_str, a["id"]))
                
                # Outbox notification
                c.execute("""
                    INSERT INTO notifications (recipient, channel, message, created_at)
                    VALUES (?, 'WhatsApp', ?, ?)
                """, (new_contact, notice_msg, now_str))
                escalated_count += 1

    conn.commit()
    return escalated_count

