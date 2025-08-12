"""
Dieses Skript `bucket_to_gemini.py` automatisiert die Verarbeitung von E-Mails im GCS-Bucket, um Kundendaten zu extrahieren, zu validieren und ggf. fehlende Informationen direkt beim Absender nachzufordern.

Ablaufübersicht:

1. **E-Mail aus GCS laden** – Rohdaten der E-Mail werden aus dem `raw/`-Bucket-Pfad gelesen.
2. **Datenextraktion mit Gemini** – Name, Vor-/Nachname, Adresse, E-Mail, Telefonnummer, PLZ, Ort werden aus dem Nachrichtentext erkannt.
3. **Validierung & Confidence** – Liste `missing` enthält alle fehlenden Pflichtfelder. Falls leer → `confidence = 1.0`; sonst wird `confidence` auf max. 0.95 begrenzt.
4. **Status setzen** – Vollständige Datensätze werden als `parsed` markiert, unvollständige als `pending`.
5. **Speichern** – Ergebnisse werden im `parsed/`-Pfad des Buckets gespeichert.
6. **Automatische Rückfrage** – Bei fehlenden Pflichtfeldern wird automatisch eine E-Mail an den Absender (`From`-Adresse) mit einer Liste der fehlenden Angaben versendet.

Vorteile:

* Direkte Nachforderung fehlender Kundendaten ohne manuelle Prüfung.
* Original-E-Mails bleiben unverändert gespeichert.
* Vollständige Datensätze können sofort weiterverarbeitet werden.
  """


import os, json, smtplib
from datetime import datetime, timedelta
from typing import Optional, List
from email.mime.text import MIMEText
from email.utils import formataddr

from dotenv import load_dotenv
from google.cloud import storage

load_dotenv()

PROJECT_ID      = os.getenv("PROJECT_ID", "pearv2")
GCS_BUCKET      = os.getenv("GCS_BUCKET", "pear-email-inbox-raw-pearv2")

PENDING_PREFIX  = os.getenv("PENDING_PREFIX", "pending/")
COMPLETE_PREFIX = os.getenv("COMPLETE_PREFIX", "complete/")
EXPIRED_PREFIX  = os.getenv("EXPIRED_PREFIX", "expired/")

# Reminder-/Ablauf-Politik
REMIND_AFTER_HOURS = int(os.getenv("REMIND_AFTER_HOURS", "48"))   # erste Erinnerung nach 48h
REMIND_EVERY_HOURS = int(os.getenv("REMIND_EVERY_HOURS", "48"))   # weitere Erinnerungen alle 48h
# Falls expires_at im Pending vorhanden ist, nutzen wir das. Sonst Fallback:
EXPIRE_AFTER_DAYS  = int(os.getenv("EXPIRE_AFTER_DAYS", "14"))

# SMTP
SMTP_HOST     = os.getenv("SMTP_HOST")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM     = os.getenv("SMTP_FROM", "PEAR Ingest <noreply@pear-app.de>")
SMTP_USE_SSL  = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

def _now() -> datetime:
    return datetime.utcnow()

def _now_iso() -> str:
    return _now().isoformat(timespec="seconds") + "Z"

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

def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts: return None
    try:
        # ISO mit 'Z' am Ende
        if ts.endswith("Z"):
            ts = ts[:-1]
        return datetime.fromisoformat(ts)
    except Exception:
        return None

def _history_add(doc: dict, event: str, extra: Optional[dict] = None):
    doc.setdefault("history", [])
    entry = {"ts": _now_iso(), "event": event}
    if extra: entry.update(extra)
    doc["history"].append(entry)

def _move_json(bucket: storage.Bucket, src_path: str, dst_path: str, doc: dict):
    # in GCS: "kopieren" = neu schreiben, dann alte löschen
    bucket.blob(dst_path).upload_from_string(
        json.dumps(doc, ensure_ascii=False, indent=2), content_type="application/json"
    )
    bucket.blob(src_path).delete()

def _needs_first_reminder(created_at: datetime, history: List[dict]) -> bool:
    # keine Erinnerung bisher?
    any_reminder = any(h.get("event") == "REMINDER_SENT" for h in history or [])
    if any_reminder:
        return False
    return _now() >= created_at + timedelta(hours=REMIND_AFTER_HOURS)

def _needs_next_reminder(last_reminder_at: datetime) -> bool:
    return _now() >= last_reminder_at + timedelta(hours=REMIND_EVERY_HOURS)

def _last_event_time(history: List[dict], event: str) -> Optional[datetime]:
    times = [_parse_iso(h.get("ts")) for h in history or [] if h.get("event") == event]
    times = [t for t in times if t]
    return max(times) if times else None

def _compose_reminder(subject: str, missing: List[str]) -> tuple[str, str]:
    sub = f"Erinnerung: Bitte ergänzen Sie fehlende Angaben – {subject or ''}".strip()
    body = ("Guten Tag,\n\n"
            "wir warten noch auf folgende fehlende Angaben:\n"
            + "".join(f"- {m}\n" for m in missing)
            + "\nSobald Sie uns diese übermitteln, schließen wir den Vorgang ab.\n\n"
            "Freundliche Grüße\nIhr PEAR-Team")
    return sub, body

def _compose_expired(subject: str) -> tuple[str, str]:
    sub = f"Vorgang abgelaufen – {subject or ''}".strip()
    body = ("Guten Tag,\n\n"
            "leider haben wir trotz Erinnerung keine Rückmeldung erhalten. "
            "Der Vorgang wurde daher vorerst geschlossen. "
            "Sie können jederzeit erneut antworten – wir öffnen den Fall dann wieder.\n\n"
            "Freundliche Grüße\nIhr PEAR-Team")
    return sub, body

def main():
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(GCS_BUCKET)

    pendings = list(bucket.list_blobs(prefix=PENDING_PREFIX))
    if not pendings:
        print("Keine pending-Fälle gefunden."); return

    print(f"Prüfe {len(pendings)} pending-Fälle...")
   
