
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
print(f"INFO: ENV geladen aus: {ENV_PATH}")

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

# DB-Variablen zentral laden
DB_HOST         = os.getenv("DB_HOST")
DB_PORT         = int(os.getenv("DB_PORT", "3306"))
DB_USER         = os.getenv("DB_USER")
DB_PASSWORD     = os.getenv("DB_PASSWORD")
DB_NAME         = os.getenv("DB_NAME")

REQ_FIELDS = [f.strip() for f in (os.getenv("REQUIRED_FIELDS") or
                                 "name,first_name,last_name,email,phone,address,plz,city").split(",") if f.strip()]

CASE_TAG_RE = re.compile(r"PEAR-([0-9a-fA-F]{8})")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY fehlt – ohne API-Key keine Extraktion möglich.")

# ---------------- DB-Check -----------------
def test_db_connection():
    """Testet, ob eine Verbindung zur MySQL-Datenbank möglich ist."""
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        print("INFO: DB-Variablen nicht vollständig in .env gesetzt. Überspringe DB-Operationen.")
        return
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        result = cursor.fetchone()
        print(f"INFO: [DB-Check] Verbindung erfolgreich: {result}")
        cursor.close()
        conn.close()
    except Error as e:
        print(f"ERROR: [DB-Check] Fehler: {e}")
        exit(1)

# ---------------- Gemini Setup ----------------
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

BASE_INSTR = (
    "Du bist ein Experte für die Extraktion deutscher Kundendaten aus E-Mails von Pflegevermittlungen.\n"
    "Extrahiere ALLE verfügbaren Informationen aus dem E-Mail-Text und strukturiere sie.\n\n"
    
    "AUSGABE-FORMAT: Nur gültiges JSON mit folgenden Feldern:\n"
    f"{', '.join(REQ_FIELDS)}, confidence, missing\n\n"
    
    "EXTRAKTIONS-REGELN:\n"
    "• NAME: Erkenne Vor- und Nachname, auch bei getrennter Angabe (Vorname: Hans, Nachname: Schmidt → name: 'Hans Schmidt')\n"
    "• TELEFON: Alle deutschen Formats: 030-123, 0221/456, +49 89 123, (089) 456-789\n"
    "• EMAIL: Standard E-Mail-Adressen\n"
    "• ADRESSE: Straße + Hausnummer, auch bei getrennter Angabe (Kastanienallee | 68 → address: 'Kastanienallee 68')\n"
    "• PLZ: 5-stellige deutsche PLZ (12345)\n"
    "• STADT: Ortsname (Berlin, München, Hamburg, etc.)\n\n"
    
    "DEUTSCHE KONTEXT-HINWEISE:\n"
    "• 'Anbei die Daten der Kundin/des Kunden' = Kundendatenübermittlung\n"
    "• 'Begleitung vereinbart' = Pflegekontext\n"
    "• Tabellen-Format erkennen: | Name | Tel | Email | Straße | Nr | PLZ | Stadt |\n"
    "• Mehrzeilige Adressen: 'Rosenweg 12\\n10115 Berlin' → address: 'Rosenweg 12', plz: '10115', city: 'Berlin'\n\n"
    
    "BEISPIELE:\n"
    "Input: 'Hans Schmidt | 089-123456 | hans@mail.de | Hauptstr. 15 | 80331 München'\n"
    "Output: {{\"name\":\"Hans Schmidt\",\"phone\":\"089-123456\",\"email\":\"hans@mail.de\",\"address\":\"Hauptstr. 15\",\"plz\":\"80331\",\"city\":\"München\"}}\n\n"
    
    "Input: 'Vorname: Maria\\nNachname: Weber\\nTelefon: 069-555\\nAdresse:\\nLindenstr. 8\\n60311 Frankfurt'\n"
    "Output: {{\"name\":\"Maria Weber\",\"phone\":\"069-555\",\"address\":\"Lindenstr. 8\",\"plz\":\"60311\",\"city\":\"Frankfurt\"}}\n\n"
    
    "WICHTIG:\n"
    "- Nur eindeutige Daten extrahieren, keine Vermutungen\n"
    "- Fehlende Felder: null setzen und in 'missing' Array auflisten\n"
    "- confidence: 1.0 nur wenn missing-Array leer, sonst 0.8-0.95\n"
    "- Bei Tabellenformat: Spalten korrekt zuordnen\n\n"
    
    "ANALYSE FOLGENDEN E-MAIL-TEXT:\n{email_body}\n\n"
    "JSON-AUSGABE:"
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
    text = re.sub(r"(?is)</p\\s*?>", "\n\n", text)
    text = re.sub(r"(?is)<.*?>", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()

def _maybe_b64_decode(s: str) -> bytes:
    if not s:
        return b""
    s_stripped = s.strip()
    if re.fullmatch(r"[A-Za-z0-9+/=\\r\\n]+", s_stripped) and len(s_stripped) % 4 == 0:
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
        print("INFO: SMTP nicht konfiguriert oder Empfänger fehlt – Versand übersprungen.")
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
        print(f"ERROR: SMTP-Fehler: {e}")
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

def save_pending_to_db(case_id: str, raw_name: str, subject: str, from_email: str, extracted: dict) -> bool:
    """Speichert Pending-Case in DB-Tabelle statt Bucket"""
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        print("INFO: DB nicht konfiguriert – überspringe Pending-Speicherung.")
        return False
    
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )
        cur = conn.cursor()
        
        case_tag = case_id[:8]
        raw_data = json.dumps(extracted, ensure_ascii=False)
        
        cur.execute("""
            INSERT INTO tbl_onboarding_pending (
                case_id, case_tag, name_vollstaendig, first_name, last_name,
                kontakt_telefon, kontakt_email, adresse_strasse, adresse_hausnummer,
                adresse_plz, adresse_ort, source_sender, source_subject, raw_data, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING')
        """, (
            case_id, case_tag, extracted.get("name"), extracted.get("first_name"), 
            extracted.get("last_name"), extracted.get("phone"), extracted.get("email"),
            extracted.get("address"), extracted.get("housenumber"), extracted.get("plz"),
            extracted.get("city"), from_email, subject, raw_data
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR: DB-Fehler beim Speichern von Pending-Case: {e}")
        return False

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

def extract_name_from_email(email: str) -> Optional[str]:
    """Extrahiert Namen aus E-Mail-Adresse für Senior-Matching"""
    if not email or "@" not in email:
        return None
    local_part = email.split("@")[0]
    # Ersetze Punkte/Unterstriche mit Leerzeichen
    name = local_part.replace(".", " ").replace("_", " ").replace("-", " ")
    # Kapitalisiere erste Buchstaben
    name = " ".join(word.capitalize() for word in name.split())
    # Mindestens 2 Wörter für Vor- und Nachname
    return name if len(name.split()) >= 2 else None

def find_pending_by_case_tag(case_tag: str) -> Optional[dict]:
    """Sucht Pending-Case anhand Case-Tag in DB"""
    if not case_tag or not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        return None
    
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )
        cur = conn.cursor(dictionary=True)
        
        cur.execute("SELECT * FROM tbl_onboarding_pending WHERE case_tag = %s AND status = 'PENDING'", (case_tag,))
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        return result
        
    except Exception as e:
        print(f"ERROR: DB-Fehler beim Case-Tag-Matching: {e}")
        return None

def find_pending_by_sender(sender: str) -> Optional[dict]:
    """Sucht neuesten Pending-Case anhand Sender in DB"""
    if not sender or not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        return None
    
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )
        cur = conn.cursor(dictionary=True)
        
        cur.execute("""
            SELECT * FROM tbl_onboarding_pending 
            WHERE source_sender = %s AND status = 'PENDING'
            ORDER BY updated_at DESC LIMIT 1
        """, (sender,))
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        return result
        
    except Exception as e:
        print(f"ERROR: DB-Fehler beim Sender-Matching: {e}")
        return None

def find_pending_by_name(name: str) -> Optional[dict]:
    """Sucht Pending-Case anhand Name in DB"""
    if not name or not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        return None
    
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )
        cur = conn.cursor(dictionary=True)
        
        cur.execute("""
            SELECT * FROM tbl_onboarding_pending 
            WHERE (name_vollstaendig LIKE %s OR CONCAT(first_name, ' ', last_name) LIKE %s)
            AND status = 'PENDING'
            ORDER BY updated_at DESC LIMIT 1
        """, (f"%{name}%", f"%{name}%"))
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        return result
        
    except Exception as e:
        print(f"ERROR: DB-Fehler beim Name-Matching: {e}")
        return None

def update_pending_case(case_id: str, new_data: dict) -> bool:
    """Aktualisiert einen Pending-Case mit neuen Daten (inkrementell)"""
    if not case_id or not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        return False
    
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )
        cur = conn.cursor()
        
        # Baue UPDATE-Statement dynamisch basierend auf verfügbaren Daten
        updates = []
        values = []
        
        field_mapping = {
            "name": "name_vollstaendig",
            "first_name": "first_name", 
            "last_name": "last_name",
            "phone": "kontakt_telefon",
            "email": "kontakt_email",
            "address": "adresse_strasse",
            "housenumber": "adresse_hausnummer", 
            "plz": "adresse_plz",
            "city": "adresse_ort"
        }
        
        for key, db_field in field_mapping.items():
            if new_data.get(key) and str(new_data[key]).strip():
                updates.append(f"{db_field} = %s")
                values.append(new_data[key])
        
        if not updates:
            return False
        
        # Aktualisiere raw_data mit merged data
        updates.append("raw_data = %s")
        values.append(json.dumps(new_data, ensure_ascii=False))
        values.append(case_id)
        
        sql = f"UPDATE tbl_onboarding_pending SET {', '.join(updates)} WHERE case_id = %s"
        cur.execute(sql, values)
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR: DB-Fehler beim Update von Pending-Case: {e}")
        return False

def complete_pending_case(case_id: str) -> bool:
    """Löscht einen abgeschlossenen Pending-Case"""
    if not case_id or not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        return False
    
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )
        cur = conn.cursor()
        
        cur.execute("DELETE FROM tbl_onboarding_pending WHERE case_id = %s", (case_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR: DB-Fehler beim Löschen von Pending-Case: {e}")
        return False

def create_database_entry(data: Dict[str, Any], source_email: str, subject: str) -> bool:
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        print("INFO: DB nicht konfiguriert – überspringe persistente Ablage (simuliere Erfolg).")
        return True
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )
        cur = conn.cursor()
        
        # Die Adresse aus den Einzelteilen zusammensetzen
        full_address = f"{(data.get('address') or '').strip()}, {(data.get('plz') or '').strip()} {(data.get('city') or '').strip()}".strip(", ")

        # SQL-Statement mit korrekten Spaltennamen aus der Doku
        cur.execute("""
            INSERT INTO tbl_kunden (name_vollstaendig, kontakt_email, kontakt_telefon, adresse_strasse, source_subject, source_from_email, raw_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get("name"),
            data.get("email"),
            data.get("phone"),
            full_address,
            subject,
            source_email,
            json.dumps(data, ensure_ascii=False)
        ))
        conn.commit()
        cid = cur.lastrowid
        cur.close()
        conn.close()
        print(f"INFO: DB: tbl_kunden.id={cid}")
        return True
    except Error as e:
        print(f"ERROR: DB-Fehler: {e}")
        return False

def main():
    # DB-Verbindung gleich am Anfang prüfen
    test_db_connection()

    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(GCS_BUCKET)

    files = list_candidates(client)
    if not files:
        print("INFO: Keine neuen Dateien zum Verarbeiten gefunden.")
        return

    print(f"INFO: Verarbeite {len(files)} Dateien...")
    for raw_name in files:
        try:
            raw_text = bucket.blob(raw_name).download_as_text()
            raw = json.loads(raw_text)
        except Exception as e:
            print(f"ERROR: Fehler beim Laden/JSON-Parse von {raw_name}: {e}")
            continue

        subject, from_addr, body = parse_raw_fields(raw)

        if not body.strip():
            print(f"INFO: {raw_name}: Kein Body extrahierbar – überspringe.")
            continue

        extracted = call_gemini(body)
        
        if not extracted:
            print(f"ERROR: Gemini-Extraktion fehlgeschlagen für {raw_name}")
            continue

        case_short = find_case_id_in_subject_or_body(subject, body)
        pending_case = None

        print(f"DEBUG: Subject='{subject}', case_short='{case_short}'")

        # Ebene 1: Case-Tag-Matching
        if case_short:
            pending_case = find_pending_by_case_tag(case_short)
            if pending_case:
                print(f"DEBUG: Found pending by case-tag: {pending_case['case_id']}")

        # Ebene 2: Sender-Matching  
        if not pending_case:
            print(f"DEBUG: No case-tag match, trying sender matching for {from_addr}")
            pending_case = find_pending_by_sender(from_addr)
            if pending_case:
                print(f"DEBUG: Found pending by sender: {pending_case['case_id']}")

        # Ebene 3: Name-Matching
        if not pending_case:
            extracted_name = extracted.get("name", "").strip()
            email_name = extract_name_from_email(from_addr)
            print(f"DEBUG: Trying name matching - extracted: '{extracted_name}', from email: '{email_name}'")
            
            if extracted_name:
                pending_case = find_pending_by_name(extracted_name)
                if pending_case:
                    print(f"DEBUG: Found pending by name matching: {pending_case['case_id']}")
            elif email_name:
                pending_case = find_pending_by_name(email_name) 
                if pending_case:
                    print(f"DEBUG: Found pending by email-name matching: {pending_case['case_id']}")

        if pending_case:
            # Bestehenden Case aktualisieren
            old_data = json.loads(pending_case.get("raw_data", "{}")) if pending_case.get("raw_data") else {}
            merged = merge_missing(old_data, extracted)
            
            if is_complete(merged, REQ_FIELDS):
                # Case vervollständigen
                ok = create_database_entry(merged, from_addr, subject)
                complete_pending_case(pending_case["case_id"])
                sub, body_mail = compose_reply(subject, [])
                if send_email(from_addr, sub, body_mail):
                    mark_responded(bucket, raw_name)
                print(f"INFO: Case {pending_case['case_id']} abgeschlossen (DB gespeichert).")
            else:
                # Partielles Update
                update_pending_case(pending_case["case_id"], merged)
                sub, body_mail = compose_reply(f"[PEAR-{pending_case['case_tag']}] – {subject or ''}".strip(), merged["missing"])
                if send_email(from_addr, sub, body_mail):
                    mark_responded(bucket, raw_name)
                print(f"INFO: Case {pending_case['case_id']} aktualisiert (fehlend: {merged['missing']}).")
            continue

        # Neuen Case erstellen
        case_id = str(uuid.uuid4())
        
        if is_complete(extracted, REQ_FIELDS):
            # Vollständiger Case - direkt in Kundentabelle
            ok = create_database_entry(extracted, from_addr, subject)
            sub, body_mail = compose_reply(subject, [])
            if send_email(from_addr, sub, body_mail):
                mark_responded(bucket, raw_name)
            print(f"INFO: Complete (sofort) angelegt und abgeschlossen: {case_id}")
        else:
            # Unvollständiger Case - in Pending-Tabelle
            save_pending_to_db(case_id, raw_name, subject, from_addr, extracted)
            case_tag = case_id[:8]
            sub, body_mail = compose_reply(f"[PEAR-{case_tag}] – {subject or ''}".strip(), extracted["missing"])
            if send_email(from_addr, sub, body_mail):
                mark_responded(bucket, raw_name)
            print(f"INFO: Pending angelegt: {case_id} (fehlend: {extracted['missing']})")


if __name__ == "__main__":
    main()
