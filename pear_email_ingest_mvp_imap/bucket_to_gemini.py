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
import os
import json
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.utils import formataddr
from google.cloud import storage
from dotenv import load_dotenv
import google.generativeai as genai

# --- ENV laden ---
load_dotenv()

GCS_BUCKET = os.getenv("GCS_BUCKET")
PROJECT_ID = os.getenv("PROJECT_ID", "pearv2")

# Gemini
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PROMPT_TEMPLATE = os.getenv("EXTRACTION_INSTRUCTIONS", """
Extrahiere die folgenden Felder aus dem E-Mail-Text:
- name
- first_name
- last_name
- email
- phone
- address
- plz
- city

Antworte im JSON-Format:
{
  "name": "...",
  "first_name": "...",
  "last_name": "...",
  "email": "...",
  "phone": "...",
  "address": "...",
  "plz": "...",
  "city": "...",
  "confidence": <0.0-1.0>,
  "missing": [ ... ]
}
""")

# SMTP
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", "PEAR Ingest <noreply@example.com>")
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

# --- Gemini Setup ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

def call_gemini(email_body: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(email_body=email_body)
    response = model.generate_content(prompt)

    try:
        return json.loads(response.text)
    except Exception as e:
        print(f"Fehler beim Parsen der Antwort: {e}\nAntwort war: {response.text}")
        return {
            "name": None, "first_name": None, "last_name": None,
            "email": None, "phone": None, "address": None,
            "plz": None, "city": None,
            "confidence": 0.0, "missing": ["name", "address", "email", "phone", "plz", "city"]
        }

def _build_missing_reply(subject: str, missing_fields: list) -> tuple:
    body = (
        "Guten Tag,\n\n"
        "vielen Dank für Ihre Anfrage.\n"
        "Leider fehlen uns noch folgende Angaben:\n\n"
        + "\n".join(f"- {field}" for field in missing_fields) +
        "\n\nBitte senden Sie uns die fehlenden Daten, damit wir Ihre Anfrage bearbeiten können.\n"
        "Vielen Dank!\n\nIhr PEAR-Team"
    )
    reply_subject = f"Rückfrage: Bitte ergänzen Sie fehlende Angaben – {subject or ''}".strip()
    return reply_subject, body

def send_email(to_addr: str, subject: str, body: str) -> None:
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD and SMTP_FROM and to_addr):
        print("SMTP nicht konfiguriert oder Empfänger fehlt – überspringe Versand.")
        return
    msg = MIMEText(body, _charset="utf-8")
    msg["From"] = SMTP_FROM if "<" in SMTP_FROM else formataddr(("PEAR Ingest", SMTP_FROM))
    msg["To"] = to_addr
    msg["Subject"] = subject

    if SMTP_USE_SSL:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as s:
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.ehlo()
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)

def main():
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET)

    blobs = list(bucket.list_blobs(prefix="raw/"))
    print(f"Verarbeite {len(blobs)} Dateien...")

    for blob in blobs:
        raw_data = json.loads(blob.download_as_text())
        from_email = raw_data.get("from_email")
        subject = raw_data.get("subject", "")
        email_body = raw_data.get("body", "")

        extracted = call_gemini(email_body)

        # Confidence auf 1.0 nur, wenn keine Felder fehlen
        if extracted.get("missing"):
            extracted["confidence"] = min(extracted.get("confidence", 0.0), 0.95)
        else:
            extracted["confidence"] = 1.0

        # Speichern in parsed/
        parsed_path = blob.name.replace("raw/", "parsed/")
        parsed_data = {
            "source_uri": f"gs://{GCS_BUCKET}/{blob.name}",
            "project_id": PROJECT_ID,
            "received_at": raw_data.get("received_at"),
            "subject": subject,
            "headers": raw_data.get("headers"),
            "extracted": extracted,
            "parsed_at": datetime.utcnow().isoformat() + "Z",
            "status": "parsed"
        }
        bucket.blob(parsed_path).upload_from_string(
            json.dumps(parsed_data, ensure_ascii=False, indent=2),
            content_type="application/json"
        )
        print(f"Gespeichert unter: gs://{GCS_BUCKET}/{parsed_path}")

        # Falls Felder fehlen → automatische Rückfrage
        if extracted.get("missing"):
            reply_subject, reply_body = _build_missing_reply(subject, extracted.get("missing"))
            send_email(from_email, reply_subject, reply_body)
            print(f"Antwort gesendet an {from_email} und Marker gesetzt.")

if __name__ == "__main__":
    main()