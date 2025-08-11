import os
import json
import uuid
import re
from datetime import datetime
from typing import Dict, Any, Optional

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
# Robuste Extraktion (Labels + Freitext DE/EN)
# ---------------------------------------------------------

_WHITESPACE = re.compile(r"\s+")

def _clean(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    s = _WHITESPACE.sub(" ", s)
    return s or None

def _join_name(vor: Optional[str], nach: Optional[str], fallback_name: Optional[str]) -> Optional[str]:
    if vor and nach:
        return _clean(f"{vor} {nach}")
    if fallback_name:
        return _clean(fallback_name)
    if vor:
        return _clean(vor)
    if nach:
        return _clean(nach)
    return None

RE_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
RE_PHONE = re.compile(r"(?i)(?:\+?\d{1,3}[\s\-\/]?)?(?:\(?0\d{1,5}\)?[\s\-\/]?)?\d[\d\s\-\/]{4,}\d")
RE_PLZ   = re.compile(r"\b(\d{5})\b")
RE_STREET = re.compile(r"(?i)\b(?:str(?:asse)?|straße|weg|platz|allee|damm|gasse|ring|ufer|chaussee)\b")
# Neue Regex für vollständige Adress- und PLZ/Ort-Erkennung
RE_ADDRESS_LINE = re.compile(
    r'(?i)\b(?:[A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*\s+)?'  # evtl. Straßenname mit Zusatz
    r'(?:str(?:asse)?|straße|weg|platz|allee|damm|gasse|ring|ufer|chaussee)\s+\d+[a-zA-Z]?\b'
)
RE_PLZ_CITY = re.compile(
    r'\b(\d{5})\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*)\b'
)
LABEL_PATTERNS = {
    "vorname":   re.compile(r"(?i)^\s*(?:vorname|first\s*name)\s*[:\-]\s*(.+)$"),
    "nachname":  re.compile(r"(?i)^\s*(?:nachname|surname|last\s*name)\s*[:\-]\s*(.+)$"),
    "name":      re.compile(r"(?i)^\s*(?:name|kunde|kundin|klient|klientin)\s*[:\-]\s*(.+)$"),
    "email":     re.compile(r"(?i)^\s*(?:e-?mail|mail)\s*[:\-]\s*(.+)$"),
    "telefon":   re.compile(r"(?i)^\s*(?:tel|telefon|phone|mobil|handy)\s*[:\-]\s*(.+)$"),
    "strasse":   re.compile(r"(?i)^\s*(?:adresse|anschrift|str(?:asse)?|straße)\s*[:\-]\s*(.+)$"),
    "plz":       re.compile(r"(?i)^\s*(?:plz|postleitzahl)\s*[:\-]\s*(\d{5})\s*$"),
    "ort":       re.compile(r"(?i)^\s*(?:ort|stadt|city)\s*[:\-]\s*(.+)$"),
    "vermittler":re.compile(r"(?i)^\s*(?:vermittlung|vermittelnde\s*stelle|tr[aä]ger)\s*[:\-]\s*(.+)$"),
}

def extract_customer_fields(body_text: str,
                            headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    text = body_text or ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    vorname = nachname = name_lbl = email_lbl = tel_lbl = None
    str_lbl = plz_lbl = ort_lbl = verm_lbl = None

    # 1) Gelabelte Zeilen bevorzugen
    for ln in lines:
        for key, pat in LABEL_PATTERNS.items():
            m = pat.match(ln)
            if m:
                val = _clean(m.group(1))
                if key == "vorname":    vorname = vorname or val
                elif key == "nachname": nachname = nachname or val
                elif key == "name":     name_lbl = name_lbl or val
                elif key == "email":    email_lbl = email_lbl or val
                elif key == "telefon":  tel_lbl = tel_lbl or val
                elif key == "strasse":  str_lbl = str_lbl or val
                elif key == "plz":      plz_lbl = plz_lbl or val
                elif key == "ort":      ort_lbl = ort_lbl or val
                elif key == "vermittler": verm_lbl = verm_lbl or val

    # 2) Fallbacks aus Freitext
    email = email_lbl or (RE_EMAIL.search(text).group(0) if RE_EMAIL.search(text) else None)

    phone = tel_lbl
    if not phone:
        m = RE_PHONE.search(text)
        if m:
            phone = _clean(m.group(0))

    plz = plz_lbl
    city = ort_lbl
    if not (plz and city):
        for ln in lines:
            if RE_PLZ.search(ln):
                if not plz:
                    plz = RE_PLZ.search(ln).group(1)
                tail = ln.split(plz, 1)[-1].strip(",;:- \t")
                if not city and tail:
                    toks = tail.split()
                    city = _clean(" ".join(toks[:3]))
            if not str_lbl and RE_STREET.search(ln):
                str_lbl = _clean(ln)

                # Erweiterte Straßensuche (auch ohne Label)
        # Erweiterte Straßensuche (auch ohne Label)
    if not str_lbl:
        RE_STREET_EXT = re.compile(
            r"(?i)\b(?:[A-ZÄÖÜ][a-zäöüß\-]+\s(?:straße|strasse|weg|platz|allee|damm|gasse|ring|ufer|chaussee))\b"
        )
        for i, ln in enumerate(lines):
            if (RE_STREET.search(ln) or RE_STREET_EXT.search(ln)) and any(ch.isdigit() for ch in ln):
                candidate = _clean(ln)
                str_lbl = candidate
                break

                # Falls PLZ und/oder Ort fehlen, im Umkreis suchen
                local_plz = plz
                local_city = city
                if not local_plz or not local_city:
                    search_range = lines[i:i+3]  # aktuelle + 2 folgende Zeilen
                    for look in search_range:
                        m_plz = RE_PLZ.search(look)
                        if m_plz and not local_plz:
                            local_plz = m_plz.group(1)
                            tail = look.split(local_plz, 1)[-1].strip(",;:- \t")
                            if not local_city and tail:
                                toks = tail.split()
                                local_city = _clean(" ".join(toks[:3]))
                        elif not local_city and look != ln and len(look.split()) <= 3:
                            # kurze Zeile könnte Ort sein
                            local_city = _clean(look)
                str_lbl = candidate
                # Falls wir hier schon PLZ/Stadt finden, übernehmen
                if not plz and local_plz:
                    plz = local_plz
                if not city and local_city:
                    city = local_city
                break      
        # Labelreste aus Adresse entfernen
    if str_lbl:
        str_lbl = re.sub(r"(?i)^(adresse|anschrift|str(?:asse)?|straße)\s*[:\-]\s*", "", str_lbl).strip()

    # Adresse zusammensetzen
    address = None
    if str_lbl and (plz and city):
        address = f"{str_lbl}, {plz} {city}"
    elif str_lbl and city:
        address = f"{str_lbl}, {city}"
    elif str_lbl:
        address = str_lbl

    # Name-Strategie
    name = _join_name(vorname, nachname, name_lbl)
    if not name:
        # heuristisch: Zeile mit 2–3 kapitalisierten Tokens ohne Ziffern und nicht Straße
        for ln in lines:
            if RE_STREET.search(ln):
                continue
            if any(ch.isdigit() for ch in ln):
                continue
            toks = [t for t in ln.split() if t[:1].isalpha()]
            capish = [t for t in toks if re.match(r"^[A-ZÄÖÜ][a-zäöüß\-]+$", t)]
            if 2 <= len(capish) <= 3:
                name = _clean(" ".join(capish))
                break

    # Fallback: Display-Name aus From-Header
    if not name and headers:
        frm = headers.get("from") or headers.get("From")
        if frm:
            m = re.match(r'(?:"?([^"<]+)"?\s*)?<.*?>', frm)
            if m and _clean(m.group(1)):
                name = _clean(m.group(1))

    vermittler = verm_lbl

    # Normalisierung
    if name:
        name = _WHITESPACE.sub(" ", name).strip()
    if city:
        city = _WHITESPACE.sub(" ", city).strip()

    # rudimentäre Konfidenz
    have = sum(x is not None for x in [name, phone, email, address, plz, city])
    confidence = int(100 * have / 6)

    out = {
        "name": name,
        "phone": phone,
        "email": email,
        "address": address,
        "plz": plz,
        "city": city,
        "vermittler": vermittler,
        "missing": [k for k, v in [("name", name), ("address", address)] if not v],
        "confidence": confidence,
    }
    return out

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
    Erwartet JSON vom imap_fetcher:
    {
      "subject": "...",
      "body": "...",
      "uid": "...",
      "headers": {"From": "...", "To": "...", "Date": "...", "Message-ID": "..."}
    }
    """
    payload = request.get_json(silent=True) or {}
    subject = payload.get("subject") or ""
    body = payload.get("body") or ""
    headers = payload.get("headers") or {}
    uid = payload.get("uid") or ""

    extracted = extract_customer_fields(body, headers=headers)

    record = {
        "project_id": PROJECT_ID,
        "received_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "subject": subject,
        "uid": uid,
        "headers": {k: headers.get(k) for k in ["From", "To", "Date", "Message-ID"] if headers.get(k)},
        "extracted": extracted,
        "raw_length": len(body),
        "status": "ok",
    }

    uri = _write_to_gcs(record)  # kann lokal None sein
    if uri:
        record["gcs_uri"] = uri

    return jsonify(record), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)