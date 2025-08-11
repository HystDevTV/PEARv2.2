"""
bucket_to_gemini.py
-------------------

Dieses Skript verarbeitet Roh-E-Mails, die im Google Cloud Storage (GCS) gespeichert sind,
extrahiert mit Hilfe des Google Gemini-API-Services relevante Kundendaten
und speichert die Ergebnisse wieder im Bucket. Zusätzlich wird – falls Daten fehlen –
automatisch eine Rückfrage-E-Mail an den Absender gesendet. Wenn alle Daten vorliegen,
wird eine Bestätigungs-E-Mail versendet.

Ablauf:
1. Verbindung zu einem definierten GCS-Bucket herstellen.
2. Alle neuen Roh-E-Mail-Dateien im Unterordner "raw/" finden, die noch nicht
   im Unterordner "parsed/" verarbeitet wurden und für die noch kein Marker in "responded/" existiert.
3. Jede Datei wird gelesen, der E-Mail-Text extrahiert und an das Gemini-Modell gesendet.
4. Gemini liefert strukturierte JSON-Daten mit den Feldern:
   - name, first_name, last_name, email, phone, address, plz, city
   - confidence (Vertrauensscore), missing (Liste fehlender Felder)
5. Die extrahierten Daten werden als JSON unter "parsed/" im Bucket gespeichert.
6. Auf Basis der Felder "missing" wird eine passende E-Mail generiert:
   - Fehlen Felder → Rückfrage-Mail mit Liste der fehlenden Angaben.
   - Alle Felder vorhanden → Bestätigungsmail.
7. Versand der E-Mail an den ursprünglichen Absender via SMTP.
8. Erstellung einer leeren Marker-Datei im Ordner "responded/", um doppelte Antworten zu verhindern.

Voraussetzungen:
- Python >= 3.10
- Abhängigkeiten: google-cloud-storage, google-generativeai, python-dotenv, smtplib
- Zugriff auf den konfigurierten Google Cloud Storage Bucket
- Gültiger Gemini API Key in der .env-Datei
- SMTP-Zugangsdaten in der .env-Datei für den E-Mail-Versand

Benötigte Umgebungsvariablen (.env):
------------------------------------
PROJECT_ID              = Google Cloud Projekt-ID
GCS_BUCKET_RAW          = Name des GCS-Buckets mit den Roh-E-Mails
RAW_PREFIX              = Pfadpräfix für die Roh-E-Mails (z. B. "raw/")
PARSED_PREFIX           = Pfadpräfix für die verarbeiteten E-Mails (z. B. "parsed/")
RESPONDED_PREFIX        = Pfadpräfix für Antwortmarker (z. B. "responded/")
BATCH_SIZE              = Anzahl zu verarbeitender E-Mails pro Durchlauf

GEMINI_MODEL            = Name des zu verwendenden Gemini-Modells (z. B. gemini-1.5-pro)
GEMINI_API_KEY          = API-Key für Gemini

SMTP_HOST               = SMTP-Serveradresse
SMTP_PORT               = SMTP-Port (Standard 587)
SMTP_USER               = Benutzername für SMTP-Login
SMTP_PASSWORD           = Passwort für SMTP-Login
SMTP_FROM               = Absenderadresse (z. B. noreply@pear-app.de)

Wichtige Hinweise:
- Die .sent-Marker-Dateien verhindern doppelten E-Mail-Versand.
- Der Confidence-Wert wird dynamisch berechnet:
  * 1.0 → alle Felder vorhanden
  * <1.0 → abhängig von der Anzahl fehlender Felder
- Der Versand erfolgt nur, wenn SMTP-Daten vollständig gesetzt sind.

"""
# bucket_to_gemini.py  — stabile One-Take-Version

# bucket_to_gemini.py — PEARv2.2 Email-Ingest → Gemini → On-Hold/Complete
# Abhängigkeiten: google-cloud-storage, google-generativeai, python-dotenv
# ENV (.env):
#   PROJECT_ID, GCS_BUCKET, RAW_PREFIX=raw/, PARSED_PREFIX=parsed/, RESPONDED_PREFIX=responded/,
#   PENDING_PREFIX=pending/, COMPLETE_PREFIX=complete/,
#   GEMINI_API_KEY, GEMINI_MODEL=gemini-1.5-pro,
#   SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_USE_SSL=true/false

import os, json, re, uuid, smtplib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from email.mime.text import MIMEText
from email.utils import formataddr

from dotenv import load_dotenv
from google.cloud import storage
import google.generativeai as genai

# ---------- ENV ----------
load_dotenv()

PROJECT_ID      = os.getenv("PROJECT_ID", "pearv2")
GCS_BUCKET      = os.getenv("GCS_BUCKET", "pear-email-inbox-raw-pearv2")
RAW_PREFIX      = os.getenv("RAW_PREFIX", "raw/")
PARSED_PREFIX   = os.getenv("PARSED_PREFIX", "parsed/")
RESP_PREFIX     = os.getenv("RESPONDED_PREFIX", "responded/")
PENDING_PREFIX  = os.getenv("PENDING_PREFIX", "pending/")
COMPLETE_PREFIX = os.getenv("COMPLETE_PREFIX", "complete/")
BATCH_SIZE      = int(os.getenv("BATCH_SIZE", "50"))

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

SMTP_HOST       = os.getenv("SMTP_HOST")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER       = os.getenv("SMTP_USER")
SMTP_PASSWORD   = os.getenv("SMTP_PASSWORD")
SMTP_FROM       = os.getenv("SMTP_FROM", "PEAR Ingest <noreply@pear-app.de>")
SMTP_USE_SSL    = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY fehlt in der .env")

# ---------- Gemini ----------
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

BASE_INSTR = (
    "Extrahiere aus folgendem deutschsprachigem E-Mail-Text Kundendaten.\n"
    "Gib ausschließlich gültiges JSON mit Feldern zurück:\n"
    "name, first_name, last_name, email, phone, address, plz, city, confidence, missing.\n"
    "Regeln:\n"
    "- Trage Felder nur ein, wenn sie im Text eindeutig vorkommen.\n"
    "- Fehlende/unklare Felder: null und in 'missing' auflisten.\n"
    "- confidence = 1.0 NUR wenn 'missing' leer ist, sonst < 1.0.\n\n"
    "E-Mail-Text:\n{email_body}\n"
)

REQ_FIELDS = ["name", "first_name", "last_name", "email", "phone", "address", "plz", "city"]

CASE_TAG_RE = re.compile(r"\[PEAR-([0-9a-fA-F]{8})\]")

# ---------- Helpers ----------
def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        first = t.find("{"); last = t.rfind("}")
        if first != -1 and last != -1:
            t = t[first:last+1]
    return t.strip()

def call_gemini(email_body: str) -> Dict[str, Any]:
    if not (email_body or "").strip():
        return {k: None for k in REQ_FIELDS} | {"confidence": 0.0, "missing": ["body"] + REQ_FIELDS}
    prompt = BASE_INSTR.format(email_body=email_body.strip())
    resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    raw = _strip_code_fences(getattr(resp, "text", "") or "")
    try:
        data = json.loads(raw)
    except Exception as e:
        print("Parser-Fehler bei Gemini-Antwort:", e)
        print("--- ROHANTWORT START ---"); print(raw); print("--- ROHANTWORT ENDE ---")
        data = {k: None for k in REQ_FIELDS} | {"confidence": 0.0, "missing": REQ_FIELDS}
    # Hard rule: confidence an missing koppeln
    missing = data.get("missing") or []
    data["confidence"] = 1.0 if len(missing) == 0 else min(float(data.get("confidence") or 0.9), 0.95)
    return data

def send_email(to_addr: Optional[str], subject: str, body: str) -> bool:
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD and SMTP_FROM and to_addr):
        print("SMTP nicht konfiguriert oder Empfänger fehlt – Versand übersprungen.")
        return False
    msg = MIMEText(body, _charset="utf-8")
    msg["From"] = SMTP_FROM if "<" in SMTP_FROM else formataddr(("PEAR Ingest", SMTP_FROM))
    msg["To"] = to_addr
    msg["Subject"] = subject
    if SMTP_USE_SSL:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as s:
            s.login(SMTP_USER, SMTP_PASSWORD); s.send_message(msg)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.ehlo(); s.starttls(); s.login(SMTP_USER, SMTP_PASSWORD); s.send_message(msg)
    return True

def compose_reply(subject: str, missing: List[str]) -> tuple[str, str]:
    if not missing:
        sub = f"Bestätigung: Ihre Angaben wurden vollständig erfasst – {subject or ''}".strip()
        body = ("Guten Tag,\n\nvielen Dank für Ihre Nachricht. "
                "Wir bestätigen, dass alle erforderlichen Angaben vollständig vorliegen.\n"
                "Wir bearbeiten Ihre Anfrage zeitnah.\n\nFreundliche Grüße\nIhr PEAR-Team")
    else:
        sub = f"Rückfrage: Bitte ergänzen Sie fehlende Angaben – {subject or ''}".strip()
        body = ("Guten Tag,\n\nvielen Dank für Ihre Nachricht. Uns fehlen leider noch folgende Angaben:\n"
                + "".join(f"- {f}\n" for f in missing)
                + "\nBitte senden Sie uns diese Informationen, damit wir fortfahren können.\n\nFreundliche Grüße\nIhr PEAR-Team")
    return sub, body

def list_candidates(client: storage.Client) -> List[str]:
    bucket = client.bucket(GCS_BUCKET)
    out = []
    for b in client.list_blobs(GCS_BUCKET, prefix=RAW_PREFIX):
        if not b.name.endswith(".json"): continue
        parsed_name = PARSED_PREFIX + b.name.split("/")[-1]
        if bucket.blob(parsed_name).exists(): continue
        responded_marker = RESP_PREFIX + b.name.split("/")[-1].replace(".json", ".sent")
        if bucket.blob(responded_marker).exists(): continue
        out.append(b.name)
        if len(out) >= BATCH_SIZE: break
    return out

def save_parsed(bucket: storage.Bucket, raw_name: str, raw_meta: dict, extracted: dict) -> str:
    parsed_name = PARSED_PREFIX + raw_name.split("/")[-1]
    payload = {
        "source_uri": f"gs://{GCS_BUCKET}/{raw_name}",
        "project_id": raw_meta.get("project_id"),
        "received_at": raw_meta.get("received_at"),
        "subject": raw_meta.get("subject"),
        "from_email": raw_meta.get("from_email"),
        "to_email": raw_meta.get("to_email"),
        "headers": raw_meta.get("headers"),
        "extracted": extracted,
        "parsed_at": _now(),
        "status": "parsed",
    }
    bucket.blob(parsed_name).upload_from_string(
        json.dumps(payload, ensure_ascii=False, indent=2), content_type="application/json"
    )
    return f"gs://{GCS_BUCKET}/{parsed_name}"

def save_pending(bucket: storage.Bucket, case_id: str, raw_name: str, subject: str,
                 from_email: Optional[str], extracted: dict) -> str:
    doc = {
        "case_id": case_id,
        "state": "PENDING_MISSING",
        "source_raw": f"gs://{GCS_BUCKET}/{raw_name}",
        "subject": subject,
        "from_email": from_email,
        "extracted": extracted,
        "history": [{"ts": _now(), "event": "CREATED"}],
        "expires_at": (datetime.utcnow() + timedelta(days=14)).isoformat(timespec="seconds") + "Z",
    }
    path = f"{PENDING_PREFIX}{case_id}.json"
    bucket.blob(path).upload_from_string(json.dumps(doc, ensure_ascii=False, indent=2), content_type="application/json")
    return f"gs://{GCS_BUCKET}/{path}"

def save_complete(bucket: storage.Bucket, case_id: str, raw_name: str, subject: str,
                  from_email: Optional[str], extracted: dict) -> str:
    doc = {
        "case_id": case_id,
        "state": "COMPLETED",
        "source_raw": f"gs://{GCS_BUCKET}/{raw_name}",
        "subject": subject,
        "from_email": from_email,
        "extracted": extracted,
        "completed_at": _now(),
    }
    path = f"{COMPLETE_PREFIX}{case_id}.json"
    bucket.blob(path).upload_from_string(json.dumps(doc, ensure_ascii=False, indent=2), content_type="application/json")
    return f"gs://{GCS_BUCKET}/{path}"

def mark_responded(bucket: storage.Bucket, raw_name: str):
    marker = RESP_PREFIX + raw_name.split("/")[-1].replace(".json", ".sent")
    bucket.blob(marker).upload_from_string("", content_type="text/plain")

def merge_missing(old: dict, new: dict) -> dict:
    """Nur fehlende Felder aus new nach old übernehmen (keine existierenden überschreiben)."""
    merged = dict(old)
    old_missing = set((old.get("missing") or []))
    for k in REQ_FIELDS:
        if (not merged.get(k)) and new.get(k):
            merged[k] = new[k]
            if k in old_missing:
                old_missing.remove(k)
    # name ableiten, falls name fehlt aber first/last vorhanden
    if not merged.get("name") and merged.get("first_name") and merged.get("last_name"):
        merged["name"] = f"{merged['first_name']} {merged['last_name']}"
        old_missing.discard("name")
    merged["missing"] = sorted(list(old_missing))
    merged["confidence"] = 1.0 if not merged["missing"] else min(float(merged.get("confidence") or 0.9), 0.95)
    return merged

def find_case_id_in_subject(subject: str) -> Optional[str]:
    m = CASE_TAG_RE.search(subject or "")
    return m.group(1) if m else None

# ---------- Main ----------
def main():
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(GCS_BUCKET)

    files = list_candidates(client)
    if not files:
        print("Keine neuen Dateien zum Verarbeiten gefunden.")
        return

    print(f"Verarbeite {len(files)} Dateien...")
    for raw_name in files:
        raw = json.loads(bucket.blob(raw_name).download_as_text())
        subject   = raw.get("subject", "")
        from_addr = raw.get("from_email")
        body      = raw.get("body") or ""

        # 1) Antwort auf bestehende Rückfrage? (Case-Code im Betreff)
        case_short = find_case_id_in_subject(subject)
        if case_short:
            # Pending-JSON suchen, das mit diesem Short-Code beginnt
            # (wir speichern full uuid; short ist die ersten 8 Zeichen)
            pendings = list(bucket.list_blobs(prefix=PENDING_PREFIX))
            target = None
            for p in pendings:
                cid = p.name.split("/")[-1].replace(".json", "")
                if cid[:8].lower() == case_short.lower():
                    target = p; break

            if target:
                pending_doc = json.loads(target.download_as_text())
                extracted_new = call_gemini(body)
                merged = merge_missing(pending_doc["extracted"], extracted_new)

                # parsed snapshot speichern (optional/weiterhin)
                save_parsed(bucket, raw_name, raw, extracted_new)

                if not merged["missing"]:
                    # fertig
                    save_complete(bucket, pending_doc["case_id"], raw_name, subject, from_addr, merged)
                    sub, body_mail = compose_reply(subject, [])
                    if send_email(from_addr, sub, body_mail): mark_responded(bucket, raw_name)
                    # Pending löschen
                    bucket.blob(target.name).delete()
                    print(f"Case {pending_doc['case_id']} abgeschlossen.")
                else:
                    # Pending aktualisieren
                    pending_doc["extracted"] = merged
                    pending_doc.setdefault("history", []).append({"ts": _now(), "event": "PARTIAL_UPDATE"})
                    bucket.blob(target.name).upload_from_string(
                        json.dumps(pending_doc, ensure_ascii=False, indent=2), content_type="application/json"
                    )
                    sub, body_mail = compose_reply(subject, merged["missing"])
                    if send_email(from_addr, sub, body_mail): mark_responded(bucket, raw_name)
                    print(f"Case {pending_doc['case_id']} aktualisiert (weiterhin fehlend).")
                continue  # nächste raw

        # 2) Neue Anfrage (kein Case-Code)
        extracted = call_gemini(body)
        save_parsed(bucket, raw_name, raw, extracted)

        if extracted.get("missing"):
            case_id = str(uuid.uuid4())
            save_pending(bucket, case_id, raw_name, subject, from_addr, extracted)
            sub, body_mail = compose_reply(f"[PEAR-{case_id[:8]}] – {subject or ''}".strip(), extracted["missing"])
            if send_email(from_addr, sub, body_mail): mark_responded(bucket, raw_name)
            print(f"Pending angelegt: {case_id}")
        else:
            case_id = str(uuid.uuid4())
            save_complete(bucket, case_id, raw_name, subject, from_addr, extracted)
            sub, body_mail = compose_reply(subject, [])
            if send_email(from_addr, sub, body_mail): mark_responded(bucket, raw_name)
            print(f"Complete angelegt: {case_id}")

if __name__ == "__main__":
    main()
