import os
import json
import uuid
from datetime import datetime
from typing import Optional

from flask import Flask, request, jsonify
from dotenv import load_dotenv

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


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)