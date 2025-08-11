"""
bucket_to_gemini.py — PEARv2.2 Email-Ingest → Gemini → Pending/Merge/Complete

Dieses Skript liest Roh-E-Mails (JSON) aus GCS (raw/), extrahiert Kundendaten mit Gemini,
speichert Snapshots (parsed/), führt eingehende Antworten mit bereits vorhandenen Pending-Daten
zusammen (Merge) und verschiebt vollständige Fälle nach complete/ (inkl. Bestätigungsmail).
Bei unvollständigen Daten legt es Pending-Fälle an/aktualisiert sie und versendet Rückfragen.

Kernprinzip: IMMER erst Pending-Ladung + Merge, DANN entscheiden (Mail/Complete/Pending-Update).

Voraussetzungen:
- Python 3.10+
- Pakete: google-cloud-storage, google-generativeai, python-dotenv
- .env mit:
    PROJECT_ID, GCS_BUCKET, RAW_PREFIX=raw/, PARSED_PREFIX=parsed/,
    RESPONDED_PREFIX=responded/, PENDING_PREFIX=pending/, COMPLETE_PREFIX=complete/,
    BATCH_SIZE, GEMINI_API_KEY, GEMINI_MODEL=gemini-1.5-pro,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_USE_SSL=true/false,
    REQUIRED_FIELDS=name,first_name,last_name,email,phone,address,plz,city,
    CASE_TAG=PEAR-  (nur informativ; Matching per Regex),
    COOLDOWN_HOURS=24
"""

import os
import re
import json
import uuid
import smtplib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from email.mime.text import MIMEText
from email.utils import formataddr
from email.header import decode_header, make_header

from dotenv import load_dotenv
from google.cloud import storage
import google.generativeai as genai

# -------------------- ENV --------------------
load_dotenv()

PROJECT_ID      = os.getenv("PROJECT_ID", "pearv2")
GCS_BUCKET      = os.getenv("GCS_BUCKET", "pear-email-inbox-raw-pearv2")

RAW_PREFIX      = os.getenv("RAW_PREFIX", "raw/")
PARSED_PREFIX   = os.getenv("PARSED_PREFIX", "parsed/")
RESP_PREFIX     = os.getenv("RESPONDED_PREFIX", "responded/")
PENDING_PREFIX  = os.getenv("PENDING_PREFIX", "pending/")
COMPLETE_PREFIX = os.getenv("COMPLETE_PREFIX", "complete/")

BATCH_SIZE      = int(os.getenv("BATCH_SIZE", "50"))
COOLDOWN_HOURS  = int(os.getenv("COOLDOWN_HOURS", "24"))

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

SMTP_HOST       = os.getenv("SMTP_HOST")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER       = os.getenv("SMTP_USER")
SMTP_PASSWORD   = os.getenv("SMTP_PASSWORD")
SMTP_FROM       = os.getenv("SMTP_FROM", "PEAR Ingest <noreply@pear-app.de>")
SMTP_USE_SSL    = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

REQ_FIELDS = [f.strip() for f in (os.getenv("REQUIRED_FIELDS") or
             "name,first_name,last_name,email,phone,address,plz,city").split(",") if f.strip()]

CASE_TAG = (os.getenv("CASE_TAG") or "PEAR-").lower()
CASE_TAG_RE = re.compile(r"\[PEAR-([0-9a-fA-F]{8})\]")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY fehlt in der .env")

# ----------------- Gemini Setup -----------------
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

BASE_INSTR = (
    "Extrahiere aus folgendem deutschsprachigem E-Mail-Text Kundendaten.\n"
    f"Gib ausschließlich gültiges JSON mit Feldern zurück: {', '.join(REQ_FIELDS)}, confidence, missing.\n"
    "Regeln:\n"
    "- Labels wie 'email', 'telefon', 'strasse', 'plz', 'ort' können mit ':' ODER mit mehreren Leerzeichen vom Wert getrennt sein.\n"
    "- Ein Label kann in einer Zeile stehen und der Wert in der NÄCHSTEN Zeile (z. B. 'strasse:' <NL> 'Lindenplatz 8').\n"
    "- PLZ und Ort können in EINER Zeile ('10115 Berlin') ODER auf ZWEI Zeilen ('10115' <NL> 'Berlin') stehen.\n"
    "- Trage Felder nur ein, wenn sie im Text eindeutig vorkommen. Fehlende/unklare Felder: null und in 'missing' auflisten.\n"
    "- confidence = 1.0 NUR wenn 'missing' leer ist, sonst < 1.0.\n\n"
    "E-Mail-Text:\n{email_body}\n"
)

# ---------- Helpers: Zeit, Decoding, Quotes ----------
def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def decode_mime_subject(s: Optional[str]) -> str:
    if not s:
        return ""
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return s or ""

RE_QUOTE_SPLIT = re.compile(r"(?is)\nAm .+ schrieb .*?:\n|^On .+ wrote:\n")
def strip_quoted_text(txt: Optional[str]) -> str:
    t = (txt or "")
    m = RE_QUOTE_SPLIT.search(t)
    if m:
        t = t[:m.start()]
    t = "\n".join(line for line in t.splitlines() if not line.strip().startswith(">"))
    return t.strip()

def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        first = t.find("{"); last = t.rfind("}")
        if first != -1 and last != -1:
            t = t[first:last+1]
    return t.strip()

# ---------- Fallback-Regex für Adressfelder ----------
RE_PLZ = re.compile(r"\b(\d{5})\b")
RE_STREET_LINE = re.compile(
    r"(?i)\b(?:str(?:asse)?|straße|str\.|weg|gasse|allee|platz|ring|damm|ufer|chaussee)\b.*\d+"
)

def _fallback_address_fields(body: str, data: dict) -> dict:
    """Füllt address/plz/city nach, wenn das Modell sie nicht geliefert hat."""
    if all(data.get(k) for k in ("address", "plz", "city")):
        return data

    lines = [ln.strip() for ln in (body or "").splitlines() if ln and ln.strip()]

    if not data.get("address"):
        for ln in lines:
            if RE_STREET_LINE.search(ln):
                addr = re.sub(r"(?i)^(adresse|anschrift|str(?:asse)?|straße|str\.)\s*[:\-]\s*", "", ln).strip()
                data["address"] = addr
                break

    plz = data.get("plz"); city = data.get("city")
    if not (plz and city):
        for ln in lines:
            m = RE_PLZ.search(ln)
            if not m:
                continue
            plz_val = m.group(1)
            tail = ln.split(plz_val, 1)[-1].strip(" ,;|-")
            if not plz:
                data["plz"] = plz_val
            if not city and tail:
                toks = [t for t in tail.split() if re.match(r"^[A-Za-zÄÖÜäöüß\-]+$", t)]
                data["city"] = " ".join(toks) if toks else tail
            break

    missing_now = [k for k in ("address", "plz", "city") if not data.get(k)]
    prev_missing = set(data.get("missing") or [])
    data["missing"] = sorted((prev_missing - {"address", "plz", "city"}) | set(missing_now))
    data["confidence"] = 1.0 if not data["missing"] else min(float(data.get("confidence") or 0.9), 0.95)
    return data

# ---------------- Gemini Call ----------------
def call_gemini(email_body: str) -> Dict[str, Any]:
    if not (email_body or "").strip():
        base = {k: None for k in REQ_FIELDS}
        base["missing"] = ["body"] + REQ_FIELDS
        base["confidence"] = 0.0
        return base
    prompt = BASE_INSTR.format(email_body=email_body.strip())
    resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    raw = _strip_code_fences(getattr(resp, "text", "") or "")
    try:
        data = json.loads(raw)
    except Exception:
        data = {k: None for k in REQ_FIELDS}
        data["missing"] = REQ_FIELDS[:]
        data["confidence"] = 0.0
    # harte Regel: 1.0 nur wenn nichts fehlt
    missing = data.get("missing") or []
    data["confidence"] = 1.0 if len(missing) == 0 else min(float(data.get("confidence") or 0.9), 0.95)
    # Fallback: address/plz/city nachziehen, wenn nötig
    if not all(data.get(k) for k in ("address", "plz", "city")):
        data = _fallback_address_fields(email_body, data)
    return data

# ---------------- Mail Compose/Send ---------------
def _fmt_known_fields(data: dict, fields: List[str]) -> str:
    lines = []
    for f in fields:
        val = data.get(f)
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        label = {
            "first_name": "Vorname",
            "last_name": "Nachname",
            "email": "E-Mail",
            "phone": "Telefon",
            "address": "Adresse",
            "plz": "PLZ",
            "city": "Ort",
            "name": "Name",
        }.get(f, f)
        lines.append(f"- {label}: {val}")
    return "\n".join(lines) if lines else "—"

def compose_reply(subject: str, missing: List[str], known: Optional[dict] = None) -> Tuple[str, str]:
    known = known or {}
    if not missing:
        reply_subject = f"Bestätigung: Ihre Angaben wurden vollständig erfasst – {subject or ''}".strip()
        body = (
            "Guten Tag,\n\n"
            "vielen Dank für Ihre Nachricht. Wir bestätigen, dass uns alle erforderlichen Angaben komplett vorliegen.\n\n"
            "Erfasste Daten:\n"
            f"{_fmt_known_fields(known, REQ_FIELDS)}\n\n"
            "Falls etwas nicht stimmt, antworten Sie bitte auf diese E-Mail und korrigieren die betreffende Zeile.\n\n"
            "Freundliche Grüße\nIhr PEAR-Team"
        )
        return reply_subject, body

    reply_subject = f"Rückfrage: Bitte ergänzen/prüfen Sie Angaben – {subject or ''}".strip()
    missing_pretty = "\n".join(f"- {f}" for f in missing) if missing else "—"
    body = (
        "Guten Tag,\n\n"
        "damit wir Ihren Fall abschließen können, benötigen wir noch die folgenden Angaben oder eine Korrektur,\n"
        "falls unten etwas falsch erkannt wurde:\n\n"
        "Fehlend:\n"
        f"{missing_pretty}\n\n"
        "Uns vorliegende Angaben (bitte kurz bestätigen oder korrigieren):\n"
        f"{_fmt_known_fields(known, REQ_FIELDS)}\n\n"
        "Antwort-Hinweis:\n"
        "- Bitte antworten Sie direkt auf diese E-Mail und senden Sie nur die fehlenden oder korrigierten Zeilen,\n"
        "  z. B. im Format:\n"
        "  Name: Max Mustermann\n"
        "  E-Mail: max@example.com\n"
        "  PLZ: 50667\n\n"
        "Vielen Dank!\n\n"
        "Freundliche Grüße\nIhr PEAR-Team"
    )
    return reply_subject, body

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
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.ehlo()
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
    return True

# ---------------- Storage Helpers ----------------
def list_candidates(client: storage.Client) -> List[str]:
    bucket = client.bucket(GCS_BUCKET)
    out = []
    for b in client.list_blobs(GCS_BUCKET, prefix=RAW_PREFIX):
        if not b.name.endswith(".json"):
            continue
        parsed_name = PARSED_PREFIX + b.name.split("/")[-1]
        if bucket.blob(parsed_name).exists():
            continue
        responded_marker = RESP_PREFIX + b.name.split("/")[-1].replace(".json", ".sent")
        if bucket.blob(responded_marker).exists():
            continue
        out.append(b.name)
        if len(out) >= BATCH_SIZE:
            break
    return out

def save_parsed(bucket: storage.Bucket, raw_name: str, raw_meta: dict, extracted: dict, subject: str) -> str:
    parsed_name = PARSED_PREFIX + raw_name.split("/")[-1]
    payload = {
        "source_uri": f"gs://{GCS_BUCKET}/{raw_name}",
        "project_id": raw_meta.get("project_id"),
        "received_at": raw_meta.get("received_at"),
        "subject": subject,
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

# ---------------- Case Matching & Merge ----------------
def find_case_id_in_subject_or_body(subject: str, body: str) -> Optional[str]:
    for txt in (subject or "", body or ""):
        m = CASE_TAG_RE.search(txt)
        if m:
            return m.group(1)
    return None

def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None

def find_pending_by_sender(bucket: storage.Bucket, sender: Optional[str]) -> Optional[str]:
    """Fallback: jüngsten Pending-Fall vom selben Absender finden (nicht abgelaufen)."""
    if not sender:
        return None
    newest: Tuple[Optional[str], Optional[datetime]] = (None, None)
    for p in bucket.list_blobs(prefix=PENDING_PREFIX):
        doc = json.loads(p.download_as_text())
        if (doc.get("from_email") or "").lower() != sender.lower():
            continue
        exp = _parse_iso(doc.get("expires_at"))
        if exp and exp < datetime.utcnow():
            continue
        # 'frischeste' Aktivität
        history = doc.get("history") or []
        ts = history[-1].get("ts") if history else doc.get("expires_at")
        t = _parse_iso(ts) or datetime.min
        if newest[1] is None or t > newest[1]:
            newest = (p.name, t)
    return newest[0]

def merge_missing(old: dict, new: dict) -> dict:
    merged = dict(old)
    old_missing = set((old.get("missing") or []))
    for k in REQ_FIELDS:
        if (not merged.get(k)) and new.get(k):
            merged[k] = new[k]
            if k in old_missing:
                old_missing.remove(k)
    if "name" in REQ_FIELDS and not merged.get("name") and merged.get("first_name") and merged.get("last_name"):
        merged["name"] = f"{merged['first_name']} {merged['last_name']}"
        old_missing.discard("name")
    merged["missing"] = sorted(list(old_missing))
    merged["confidence"] = 1.0 if not merged["missing"] else min(float(merged.get("confidence") or 0.9), 0.95)
    return merged

def cooldown_ok(pending_doc: dict) -> bool:
    """Erlaubt erneuten Versand erst nach COOLDOWN_HOURS seit letztem MAIL_SENT."""
    history = pending_doc.get("history") or []
    last_mail = None
    for ev in reversed(history):
        if ev.get("event") == "MAIL_SENT":
            last_mail = _parse_iso(ev.get("ts"))
            break
    if not last_mail:
        return True
    return datetime.utcnow() - last_mail >= timedelta(hours=COOLDOWN_HOURS)

# ---------------- DB-Hook (Stub) ----------------
def create_customer_in_db(data: dict) -> str:
    """
    Stub: hier später echten MySQL-Insert implementieren.
    Erwartet vollständiges 'merged'-Dict. Gibt kunden_id/uuid zurück.
    """
    return str(uuid.uuid4())

# -------------------- MAIN --------------------
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
        subject  = decode_mime_subject(raw.get("subject", ""))
        from_addr = raw.get("from_email")
        body_raw = raw.get("body") or ""
        body     = strip_quoted_text(body_raw)

        # 0) Snapshot (parsed/) – gut für Debug/Transparenz
        extracted = call_gemini(body)
        save_parsed(bucket, raw_name, raw, extracted, subject)

        # 1) Case suchen: Tag im Betreff/Body, sonst Fallback: Absender
        case_short = find_case_id_in_subject_or_body(subject, body)
        pending_path = None
        if case_short:
            for p in bucket.list_blobs(prefix=PENDING_PREFIX):
                cid = p.name.split("/")[-1].replace(".json", "")
                if cid[:8].lower() == case_short.lower():
                    pending_path = p.name
                    break
        if not pending_path:
            pending_path = find_pending_by_sender(bucket, from_addr)

        # 2) Entscheiden NACH Merge
        if pending_path:
            pending_doc = json.loads(bucket.blob(pending_path).download_as_text())
            merged = merge_missing(pending_doc["extracted"], extracted)

            if not merged["missing"]:
                # DB → complete → Bestätigung → responded → pending löschen
                _ = create_customer_in_db(merged)
                save_complete(bucket, pending_doc["case_id"], raw_name, subject, from_addr, merged)
                sub, body_mail = compose_reply(subject, [], known=merged)
                if send_email(from_addr, sub, body_mail):
                    mark_responded(bucket, raw_name)
                    pending_doc.setdefault("history", []).append({"ts": _now(), "event": "MAIL_SENT"})
                bucket.blob(pending_path).delete()
                print(f"Case {pending_doc['case_id']} abgeschlossen.")
            else:
                # weiterhin pending: nur senden, wenn Cooldown OK
                pending_doc["extracted"] = merged
                pending_doc.setdefault("history", []).append({"ts": _now(), "event": "PARTIAL_UPDATE"})
                if cooldown_ok(pending_doc):
                    sub, body_mail = compose_reply(subject, merged["missing"], known=merged)
                    if send_email(from_addr, sub, body_mail):
                        mark_responded(bucket, raw_name)
                        pending_doc["history"].append({"ts": _now(), "event": "MAIL_SENT"})
                # persist pending update
                bucket.blob(pending_path).upload_from_string(
                    json.dumps(pending_doc, ensure_ascii=False, indent=2),
                    content_type="application/json"
                )
                print(f"Case {pending_doc['case_id']} aktualisiert (weiterhin fehlend).")
            continue

        # 3) Kein bestehender Case → neu
        if extracted.get("missing"):
            case_id = str(uuid.uuid4())
            save_pending(bucket, case_id, raw_name, subject, from_addr, extracted)
            subj_with_tag = f"[PEAR-{case_id[:8]}] – {subject or ''}".strip()
            sub, body_mail = compose_reply(subj_with_tag, extracted["missing"], known=extracted)
            if send_email(from_addr, sub, body_mail):
                mark_responded(bucket, raw_name)
                # mini-pending laden & MAIL_SENT eintragen (für Cooldown beim nächsten Mal)
                path = f"{PENDING_PREFIX}{case_id}.json"
                pdoc = json.loads(bucket.blob(path).download_as_text())
                pdoc.setdefault("history", []).append({"ts": _now(), "event": "MAIL_SENT"})
                bucket.blob(path).upload_from_string(
                    json.dumps(pdoc, ensure_ascii=False, indent=2), content_type="application/json"
                )
            print(f"Pending angelegt: {case_id}")
        else:
            case_id = str(uuid.uuid4())
            _ = create_customer_in_db(extracted)
            save_complete(bucket, case_id, raw_name, subject, from_addr, extracted)
            sub, body_mail = compose_reply(subject, [], known=extracted)
            if send_email(from_addr, sub, body_mail):
                mark_responded(bucket, raw_name)
            print(f"Complete angelegt: {case_id}")

if __name__ == "__main__":
    main()
