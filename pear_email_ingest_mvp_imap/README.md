# PEAR Email Ingest MVP (IMAP → Cloud → Reply)

Dieser Build nutzt **IMAP** (kein Gmail OAuth) und filtert E-Mails nach Betreff:
- Enthält: `Anfrage` oder `Kundendaten` oder `Klientendaten` (case-insensitive)

**Ablauf:**
1) IMAP: holt ungelesene Mails mit passendem Betreff
2) POST an `/ingest` des Flask-Services (lokal oder Cloud Run)
3) Service speichert Rohdaten (optional GCS), ruft Gemini (optional), schreibt MySQL, sendet SMTP-Antwort

## Schnellstart
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.sample .env  # ist bereits mit postboy@pear-app.de vorbelegt
python main.py  # startet API auf :8080
python imap_fetcher.py  # holt Mails und postet an /ingest
```
