"""
bucket_to_gemini.py — PEARv2.2
RAW (E-Mails) → PENDING (Zwischenstände) → bei Vollständigkeit: DB + Bestätigung + PENDING löschen

- Liest neue RAW-JSONs aus GCS (prefix raw/).
- Extrahiert Kundendaten via Gemini.
- Sucht zugehörigen Pending-Case (Betreff-Tag [PEAR-XXXXXXXX] → Fallback: Absender).
- Merged Felder; wenn vollständig: DB speichern, Bestätigung senden, Pending löschen.
  Sonst: Pending aktualisieren und Rückfrage schicken.
- Antwort-Marker unter responded/ verhindert Doppelversand.

ENV (Beispiele):
  PROJECT_ID, GCS_BUCKET
  RAW_PREFIX=raw/, PENDING_PREFIX=pending/, RESPONDED_PREFIX=responded/, BATCH_SIZE=50
  GEMINI_API_KEY, GEMINI_MODEL=gemini-1.5-pro
  REQUIRED_FIELDS=name,first_name,last_name,email,phone,address,plz,city
  SMTP_HOST, SMTP_PORT=587, SMTP_USER, SMTP_PASSWORD, SMTP_FROM="PEAR Ingest" <postboy@pear-app.de>, SMTP_USE_SSL=false
  DB_HOST, DB_PORT=3306, DB_USER, DB_PASSWORD, DB_NAME
"""

import os, json, re, uuid, smtplib, base64
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from email.mime.text import MIMEText
from email.utils import formataddr
from email.header import decode_header, make_header
from email import policy
from email.parser import BytesParser
from dotenv import load_dotenv
from google.cloud import storage
import google.generativeai as genai
import mysql.connector
from mysql.connector import Error

# ---------------- ENV-Setup ----------------
# Immer die .env im Hauptprojekt-Ordner laden, egal von wo das Script gestartet wird
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path=ENV_PATH, override=True)

print(f"[DEBUG] ENV geladen aus: {ENV_PATH}")
print("[DEBUG] DB_USER:", os.getenv("DB_USER"))
print("[DEBUG] DB_PASSWORD:", os.getenv("DB_PASSWORD"))
print("[DEBUG] DB_HOST:", os.getenv("DB_HOST"))
print("[DEBUG] DB_NAME:", os.getenv("DB_NAME"))

# ---------------- DB-Check -----------------
def test_db_connection():
    """Testet, ob eine Verbindung zur DB-Datenbank möglich ist."""
    try:
        conn = DB.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        result = cursor.fetchone()
        print(f"[DB-Check] Verbindung erfolgreich: {result}")
        cursor.close()
        conn.close()
    except Error as e:
        print(f"[DB-Check] Fehler: {e}")
        exit(1)

# Gleich beim Start prüfen
test_db_connection()

# ---------------- ENV-Variablen laden ----------------
PROJECT_ID      = os.getenv("PROJECT_ID", "pearv2")
GCS_BUCKET      = os.getenv("GCS_BUCKET", "pear-email-inbox-raw-pearv2")

RAW_PREFIX      = os.getenv("RAW_PREFIX", "raw/")
PENDING_PREFIX  = os.getenv("PENDING_PREFIX", "pending/")
RESP_PREFIX     = os.getenv("RESPONDED_PREFIX", "responded/")
BATCH_SIZE      = int(os.getenv("BATCH_SIZE", "50"))

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

SMTP_HOST       = os.getenv("SMTP_HOST")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER       = os.getenv("SMTP_USER")
SMTP_PASSWORD   = os.getenv("SMTP_PASSWORD")
SMTP_FROM       = os.getenv("SMTP_FROM", "PEAR Ingest <noreply@pear-app.de>")
SMTP_USE_SSL    = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

DB_HOST      = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT      = int(os.getenv("DB_PORT", "3306"))
DB_USER      = os.getenv("DB_USER", "app_user")
DB_PASSWORD  = os.getenv("DB_PASSWORD", "TempPass123!")
DB_NAME      = os.getenv("DB_NAME", "pear_app_db")

REQ_FIELDS = [f.strip() for f in (os.getenv("REQUIRED_FIELDS") or
                                 "name,first_name,last_name,email,phone,address,plz,city").split(",") if f.strip()]

CASE_TAG_RE = re.compile(r"\[PEAR-([0-9a-fA-F]{8})\]")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY fehlt – ohne API-Key keine Extraktion möglich.")

# ---------------- Gemini Setup ----------------
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

BASE_INSTR = (
    "Extrahiere aus folgendem deutschsprachigem E-Mail-Text Kundendaten.\n"
    f"Gib ausschließlich gültiges JSON mit Feldern zurück: {', '.join(REQ_FIELDS)}, confidence, missing.\n"
    "Regeln:\n"
    "- Trage Felder nur ein, wenn sie im Text eindeutig vorkommen.\n"
    "- Fehlende/unklare Felder: null und in 'missing' auflisten.\n"
    "- confidence = 1.0 NUR wenn 'missing' leer ist, sonst < 1.0.\n\n"
    "E-Mail-Text:\n{email_body}\n"
)

# ---------------- Helper-Funktionen ----------------
def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def decode_mime_subject(subject: Optional[str]) -> str:
    if not subject:
        return ""
    try:
        return str(make_header(decode_header(subject)))
    except Exception:
        return subject

def _html_to_text(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", "", html)
    text = re.sub(r"(?is)<br\\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p\\s*>", "\n\n", text)
    text = re.sub(r"(?is)<.*?>", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()

def _maybe_b64_decode(s: str) -> bytes:
    if not s:
        return b""
    s_stripped = s.strip()
    if re.fullmatch(r"[A-Za-z0-9+/=\r\n]+", s_stripped) and len(s_stripped) % 4 == 0:
        try:
            return base64.b64decode(s_stripped, validate=True)
        except Exception:
            pass
    return s.encode("utf-8", errors="ignore")

def _extract_from_mime(raw_mime: str) -> tuple[str, str, str]:
    msg_bytes = _maybe_b64_decode(raw_mime)
    try:
        msg = BytesParser(policy=policy.default).parsebytes(msg_bytes)
    except Exception:
        return "", "", ""
    subj = decode_mime_subject(str(msg["subject"]) if msg["subject"] else "")
    frm = str(msg["from"] or "").strip()
    body_text = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type() or ""
            if ctype.lower() == "text/plain":
                try:
                    body_text = part.get_content().strip()
                    break
                except Exception:
                    continue
        if not body_text:
            for part in msg.walk():
                ctype = part.get_content_type() or ""
                if ctype.lower() == "text/html":
                    try:
                        body_text = _html_to_text(part.get_content())
                        break
                    except Exception:
                        continue
    else:
        ctype = msg.get_content_type() or ""
        try:
            content = msg.get_content()
        except Exception:
            content = ""
        if ctype.lower() == "text/plain":
            body_text = (content or "").strip()
        elif ctype.lower() == "text/html":
            body_text = _html_to_text(content or "")
    return subj or "", frm or "", body_text or ""

def parse_raw_fields(raw: dict) -> tuple[str, str, str]:
    subject = decode_mime_subject(raw.get("subject") or "")
    from_email = (raw.get("from_email") or raw.get("from") or "").strip()
    body = (raw.get("body") or "").strip()
    headers = raw.get("headers") or {}
    if not subject:
        h_subj = headers.get("Subject") or headers.get("subject")
        if h_subj:
            subject = decode_mime_subject(h_subj)
    if not from_email:
        h_from = headers.get("From") or headers.get("from")
        if h_from:
            from_email = str(h_from).strip()
    if not (subject and from_email and body):
        for key in ("raw_mime", "mime", "raw"):
            raw_mime = raw.get(key)
            if raw_mime:
                m_subj, m_from, m_body = _extract_from_mime(raw_mime)
                subject = subject or m_subj
                from_email = from_email or m_from
                body = body or m_body
                break
    return subject or "", from_email or "", body or ""

def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        first = t.find("{")
        last = t.rfind("}")
        if first != -1 and last != -1:
            t = t[first:last+1]
    return t.strip()

def call_gemini(email_body: str) -> Dict[str, Any]:
    if not (email_body or "").strip():
        base = {k: None for k in REQ_FIELDS}
        base["missing"] = REQ_FIELDS[:]
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
    missing = data.get("missing") or [f for f in REQ_FIELDS if not (data.get(f) or "").strip()]
    data["missing"] = missing
    data["confidence"] = 1.0 if not missing else min(float(data.get("confidence") or 0.9), 0.95)
    return data

def send_email(to_addr: Optional[str], subject: str, body: str) -> bool:
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD and SMTP_FROM and to_addr):
        print("SMTP nicht konfiguriert oder Empfänger fehlt – Versand übersprungen.")
        return False
    msg = MIMEText(body, _charset="utf-8")
    msg["From"] = SMTP_FROM if "<" in SMTP_FROM else formataddr(("PEAR Ingest", SMTP_FROM))
    msg["To"] = to_addr
    msg["Subject"] = subject
    try:
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
    except Exception as e:
        print(f"SMTP-Fehler: {e}")
        return False

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

def is_complete(data: dict, required_fields: List[str]) -> bool:
    return all((data.get(f) is not None and str(data.get(f)).strip() != "") for f in required_fields)

def list_candidates(client: storage.Client) -> List[str]:
    out = []
    bucket = client.bucket(GCS_BUCKET)
    for b in client.list_blobs(GCS_BUCKET, prefix=RAW_PREFIX):
        if not b.name.endswith(".json"):
            continue
        marker = RESP_PREFIX + b.name.split("/")[-1].replace(".json", ".sent")
        if bucket.blob(marker).exists():
            continue
        out.append(b.name)
        if len(out) >= BATCH_SIZE:
            break
    return out

def mark_responded(bucket: storage.Bucket, raw_name: str):
    marker = RESP_PREFIX + raw_name.split("/")[-1].replace(".json", ".sent")
    bucket.blob(marker).upload_from_string("", content_type="text/plain")

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
    return path

def merge_missing(old: dict, new: dict) -> dict:
    merged = dict(old or {})
    old_missing = set((old or {}).get("missing") or [])
    for k in REQ_FIELDS:
        if (not (merged.get(k) and str(merged.get(k)).strip())) and (new.get(k) and str(new.get(k)).strip()):
            merged[k] = new[k]
            if k in old_missing:
                old_missing.remove(k)
    if "name" in REQ_FIELDS and not (merged.get("name") or "").strip():
        if merged.get("first_name") and merged.get("last_name"):
            merged["name"] = f"{merged['first_name']} {merged['last_name']}"
            old_missing.discard("name")
    merged["missing"] = sorted(list(old_missing or [f for f in REQ_FIELDS if not (merged.get(f) and str(merged.get(f)).strip())]))
    merged["confidence"] = 1.0 if not merged["missing"] else min(float((old or {}).get("confidence") or new.get("confidence") or 0.9), 0.95)
    return merged

def find_case_id_in_subject_or_body(subject: str, body: str) -> Optional[str]:
    for txt in (subject or "", body or ""):
        m = CASE_TAG_RE.search(txt)
        if m:
            return m.group(1)
    return None

def find_pending_by_sender(bucket: storage.Bucket, sender: Optional[str]) -> Optional[str]:
    if not sender:
        return None
    newest: tuple[Optional[str], Optional[datetime]] = (None, None)
    for p in bucket.list_blobs(prefix=PENDING_PREFIX):
        if not p.name.endswith(".json"):
            continue
        try:
            doc = json.loads(p.download_as_text())
        except Exception:
            continue
        if (doc.get("from_email") or "").lower() != sender.lower():
            continue
        ts = (doc.get("history") or [{}])[-1].get("ts") or doc.get("expires_at")
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None
        except Exception:
            t = None
        if newest[1] is None or (t and t > newest[1]):
            newest = (p.name, t)
    return newest[0]

def create_database_entry(data: Dict[str, Any], source_email: str, subject: str) -> bool:
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        print("DB nicht konfiguriert – überspringe persistente Ablage (simuliere Erfolg).")
        return True
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO tbl_kunden (name, email, phone, address, source_subject, source_from_email, raw_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get("name"),
            data.get("email"),
            data.get("phone"),
            f"{(data.get('address') or '').strip()}, {(data.get('plz') or '').strip()} {(data.get('city') or '').strip()}".strip(", "),
            subject,
            source_email,
            json.dumps(data, ensure_ascii=False)
        ))
        conn.commit()
        cid = cur.lastrowid
        cur.close(); conn.close()
        print(f"DB: tbl_kunden.id={cid}")
        return True
    except Exception as e:
        print(f"DB-Fehler: {e}")
        return False

def main():
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(GCS_BUCKET)

    files = list_candidates(client)
    if not files:
        print("Keine neuen Dateien zum Verarbeiten gefunden.")
        return

    print(f"Verarbeite {len(files)} Dateien...")
    for raw_name in files:
        try:
            raw_text = bucket.blob(raw_name).download_as_text()
            raw = json.loads(raw_text)
        except Exception as e:
            print(f"Fehler beim Laden/JSON-Parse von {raw_name}: {e}")
            continue

        subject, from_addr, body = parse_raw_fields(raw)

        if not body.strip():
            print(f"{raw_name}: Kein Body extrahierbar – überspringe.")
            continue

        extracted = call_gemini(body)

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

        if pending_path:
            pending_doc = json.loads(bucket.blob(pending_path).download_as_text())
            merged = merge_missing(pending_doc.get("extracted"), extracted)

            if is_complete(merged, REQ_FIELDS):
                ok = create_database_entry(merged, from_addr, subject)
                sub, body_mail = compose_reply(subject, [])
                if send_email(from_addr, sub, body_mail):
                    mark_responded(bucket, raw_name)
                bucket.blob(pending_path).delete()
                print(f"Case {pending_doc['case_id']} abgeschlossen (DB gespeichert).")
            else:
                pending_doc["extracted"] = merged
                pending_doc.setdefault("history", []).append({"ts": _now(), "event": "PARTIAL_UPDATE"})
                bucket.blob(pending_path).upload_from_string(
                    json.dumps(pending_doc, ensure_ascii=False, indent=2),
                    content_type="application/json"
                )
                sub, body_mail = compose_reply(subject, merged["missing"])
                if send_email(from_addr, sub, body_mail):
                    mark_responded(bucket, raw_name)
                print(f"Case {pending_doc['case_id']} aktualisiert (fehlend: {merged['missing']}).")
            continue

        case_id = str(uuid.uuid4())
        path = save_pending(bucket, case_id, raw_name, subject, from_addr, extracted)

        if is_complete(extracted, REQ_FIELDS):
            ok = create_database_entry(extracted, from_addr, subject)
            sub, body_mail = compose_reply(subject, [])
            if send_email(from_addr, sub, body_mail):
                mark_responded(bucket, raw_name)
            bucket.blob(path).delete()
            print(f"Complete (sofort) angelegt und abgeschlossen: {case_id}")
        else:
            sub, body_mail = compose_reply(f"[PEAR-{case_id[:8]}] – {subject or ''}".strip(), extracted["missing"])
            if send_email(from_addr, sub, body_mail):
                mark_responded(bucket, raw_name)
            print(f"Pending angelegt: {case_id} (fehlend: {extracted['missing']})")


if __name__ == "__main__":
    main()

