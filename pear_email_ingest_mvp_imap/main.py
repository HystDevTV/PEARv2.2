import os
import json
import uuid
from datetime import datetime
from typing import Optional
import threading
import time
import subprocess
import logging

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from email_guardian import EmailGuardian

# GCS optional (lokal darf es auch ohne laufen)
try:
    from google.cloud import storage  # pip install google-cloud-storage
    _HAS_GCS = True
except Exception:
    _HAS_GCS = False

# ---------------------------------------------------------
# Env laden
# ---------------------------------------------------------
load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID", "")
REGION = os.getenv("REGION", "europe-west3")
# Wir akzeptieren mehrere Key-Namen, falls sich was ändert:
GCS_BUCKET = (
    os.getenv("GCS_BUCKET")
    or os.getenv("GCP_BUCKET")
    or os.getenv("GCS_BUCKET_NAME")
)

# ---------------------------------------------------------
# Flask-App
# ---------------------------------------------------------
app = Flask(__name__)

# Email processing configuration
EMAIL_CHECK_INTERVAL = int(os.getenv('EMAIL_CHECK_INTERVAL', 300))  # 5 minutes default
AUTO_EMAIL_PROCESSING = os.getenv('AUTO_EMAIL_PROCESSING', 'true').lower() == 'true'

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.get("/healthz")
def healthz():
    return {"status": "ok", "project": PROJECT_ID, "bucket": GCS_BUCKET}, 200


def _write_to_gcs(obj: dict, suffix: str = "json") -> Optional[str]:
    if not (_HAS_GCS and GCS_BUCKET):
        return None
    client = storage.Client()  # nutzt ADC (gcloud auth application-default login)
    bucket = client.bucket(GCS_BUCKET)
    blob_id = f"raw/{uuid.uuid4()}.{suffix}"
    blob = bucket.blob(blob_id)
    blob.upload_from_string(
        json.dumps(obj, ensure_ascii=False, indent=2),
        content_type="application/json",
    )
    app.logger.info(f"UPLOAD OK -> gs://{GCS_BUCKET}/{blob_id}")
    return f"gs://{GCS_BUCKET}/{blob_id}"


@app.post("/ingest")
def ingest():
    """
    Erwartet Rohdaten vom imap_fetcher:
    {
      "subject": "...",
      "from_email": "...",
      "to_email": "...",
      "body": "..."
    }
    """
    payload = request.get_json(silent=True) or {}

    record = {
        "project_id": PROJECT_ID,
        "received_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "subject": payload.get("subject"),
        "from_email": payload.get("from_email"),
        "to_email": payload.get("to_email"),
        "body": payload.get("body"),
        "raw_length": len(payload.get("body") or ""),
        "status": "ok"
    }

    uri = _write_to_gcs(record)  # kann lokal None sein
    if uri:
        record["gcs_uri"] = uri

    return jsonify(record), 200


@app.post("/process-emails")
def process_emails_manual():
    """Manual endpoint to trigger email processing"""
    success = run_email_processing()
    return jsonify({
        "status": "success" if success else "error",
        "message": "Email processing completed" if success else "Email processing failed"
    }), 200 if success else 500


@app.get("/guardian-status")
def guardian_status():
    """Get Guardian system status"""
    guardian = EmailGuardian()
    result = guardian.guardian_check()
    
    return jsonify({
        "guardian_active": True,
        "allow_processing": result.allow_processing,
        "threat_level": guardian.evaluate_threat_level(result.stats),
        "reason": result.reason,
        "action": result.action,
        "stats": {
            "pending_cases": result.stats.pending_cases,
            "suspicious_patterns": result.stats.suspicious_patterns
        },
        "emergency_lockdown": guardian.check_emergency_lockdown()
    })


@app.post("/guardian-unlock")
def guardian_unlock():
    """Manual emergency lockdown unlock"""
    guardian = EmailGuardian()
    
    if guardian.check_emergency_lockdown():
        guardian.deactivate_emergency_lockdown()
        return jsonify({"message": "Emergency lockdown deactivated", "status": "unlocked"})
    else:
        return jsonify({"message": "No active lockdown", "status": "normal"})


def run_imap_fetcher():
    """Run IMAP fetcher"""
    try:
        logger.info("🔍 Starting IMAP fetcher...")
        result = subprocess.run(['python', 'imap_fetcher.py'], 
                              capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            logger.info("✅ IMAP fetcher successful")
            return True
        else:
            logger.error(f"❌ IMAP fetcher error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("⏰ IMAP fetcher timeout")
        return False
    except Exception as e:
        logger.error(f"💥 IMAP fetcher exception: {e}")
        return False


def run_bucket_processor():
    """Run bucket-to-gemini processor"""
    try:
        logger.info("🧠 Starting bucket processor...")
        result = subprocess.run(['python', 'bucket_to_gemini.py'], 
                              capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logger.info("✅ Bucket processor successful")
            # Log important outputs
            if "DB: tbl_kunden.id=" in result.stdout:
                logger.info("🎉 New customers created!")
            if "Case" in result.stdout and "abgeschlossen" in result.stdout:
                logger.info("📋 Cases completed!")
            return True
        else:
            logger.error(f"❌ Bucket processor error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("⏰ Bucket processor timeout")
        return False
    except Exception as e:
        logger.error(f"💥 Bucket processor exception: {e}")
        return False


def run_email_processing():
    """Complete email processing cycle"""
    logger.info("🚀 Starting email processing...")
    
    # 0. Guardian check - the "Spion"
    guardian = EmailGuardian()
    guardian_result = guardian.guardian_check()
    
    if not guardian_result.allow_processing:
        logger.error(f"🛡️ GUARDIAN BLOCKED: {guardian_result.reason}")
        logger.error(f"🚨 Action: {guardian_result.action}")
        
        if guardian_result.action == "EMERGENCY_LOCKDOWN":
            logger.critical("🚨🚨 SYSTEM IN EMERGENCY LOCKDOWN! 🚨🚨")
        
        return False
    
    logger.info(f"🛡️ Guardian approved: {guardian_result.reason}")
    
    # 1. Fetch emails
    fetch_success = run_imap_fetcher()
    
    if fetch_success:
        # 2. Short wait between operations
        time.sleep(2)
        
        # 3. Process emails
        process_success = run_bucket_processor()
        
        if process_success:
            logger.info("✨ Email processing completed successfully")
            return True
        else:
            logger.warning("⚠️ Email processing partially failed")
            return False
    else:
        logger.warning("⚠️ Email fetch failed, skipping processing")
        return False


def email_processing_worker():
    """Background worker for automatic email processing"""
    logger.info(f"🤖 Email processing worker started (interval: {EMAIL_CHECK_INTERVAL}s)")
    
    while AUTO_EMAIL_PROCESSING:
        try:
            run_email_processing()
            time.sleep(EMAIL_CHECK_INTERVAL)
        except Exception as e:
            logger.error(f"💥 Email processing worker error: {e}")
            time.sleep(60)  # Wait 1 minute before retry


def start_background_email_processing():
    """Start background email processing if enabled"""
    if AUTO_EMAIL_PROCESSING:
        worker_thread = threading.Thread(target=email_processing_worker, daemon=True)
        worker_thread.start()
        logger.info("🔄 Background email processing started")
    else:
        logger.info("⏸️ Automatic email processing disabled")


if __name__ == "__main__":
    # Start background email processing
    start_background_email_processing()
    
    port = int(os.getenv("PORT", "8080"))
    logger.info(f"🌐 Starting Flask server on port {port}")
    logger.info(f"📧 Auto email processing: {'ON' if AUTO_EMAIL_PROCESSING else 'OFF'} (interval: {EMAIL_CHECK_INTERVAL}s)")
    app.run(host="0.0.0.0", port=port)