# 📚 PEAR Projektdokumentation

Diese Dokumentation umfasst drei eng verbundene Projekte innerhalb einer gemeinsamen Codebasis:

---

## 🏠 PEARv2 (Hauptprojekt)
Eine Webanwendung zur Digitalisierung administrativer Aufgaben in der Seniorenpflege.

- **Version**: 0.1.1  
- **Status**: In Entwicklung  
- **Dokumentation**: [PEARv2 Dokumentation](./pearv2/README.md)

---

## 🤖 dev-team-pear (Automatisierungsprojekt)
Ein KI-gestütztes Automatisierungssystem für Entwicklungsteams.

- **Version**: 1.0.0  
- **Status**: Aktiv  
- **Dokumentation**: [Dev-Team-PEAR Dokumentation](./dev-team-pear/README.md)

---

## 📧 pear_email_ingest_mvp_imap (E-Mail Ingest MVP)
**Zweck:** Minimalversion einer E-Mail-Ingest-Pipeline für das PEAR-System.  
Das Modul ruft E-Mails via IMAP ab, prüft anhand konfigurierbarer Keywords im Betreff und speichert sie unverändert im Google Cloud Storage.  
Die eigentliche Feldextraktion (Parsing) erfolgt **nicht** hier, sondern später durch den Gemini-Prozess.

### Funktionsweise
1. **IMAP-Fetcher** (`imap_fetcher.py`)
   - Verbindet sich mit dem IMAP-Server (z. B. `server7.rainbow-web.com`).
   - Liest ungelesene Mails.
   - Filtert nach Betreff-Keywords (z. B. `Kundendaten`, `Klientendaten`).
   - Sendet die Rohdaten via POST an den `/ingest`-Endpoint.

2. **Ingest-API** (`main.py`)
   - Flask-API, die die empfangenen Daten im JSON-Format in den GCS-Bucket schreibt.
   - Ergänzt Metadaten (`project_id`, `received_at`, `raw_length`).
   - Keine Interpretation oder Extraktion der Inhalte.

---

## ⚙️ Installation
```bash
cd pear_email_ingest_mvp_imap
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
🛠 .env Beispiel
env
Kopieren
Bearbeiten
IMAP_SERVER=server7.rainbow-web.com
IMAP_USER=postfach@example.com
IMAP_PASSWORD=deinpasswort
KEYWORDS=Kundendaten,Kunden,Klientendaten
INGEST_URL=http://localhost:5000/ingest
GCS_BUCKET=pear-email-inbox-raw-pearv2
PROJECT_ID=pearv2
🚀 Nutzung
API starten

bash
Kopieren
Bearbeiten
python main.py
Fetcher ausführen

bash
Kopieren
Bearbeiten
python imap_fetcher.py
E-Mails werden gespeichert unter:

bash
Kopieren
Bearbeiten
gs://pear-email-inbox-raw-pearv2/raw/<uuid>.json
🔗 Projektbeziehung
dev-team-pear unterstützt die Entwicklung von PEARv2 durch Automatisierung von Entwicklungsprozessen.

pear_email_ingest_mvp_imap liefert Rohdaten in den GCS-Bucket, die anschließend in PEARv2 oder einer separaten Datenverarbeitungs-Pipeline (z. B. mit Gemini) weiterverarbeitet werden.

📂 Projektstruktur
pgsql
Kopieren
Bearbeiten
PEARV2.2/
├── .venv/
├── design-variants/
├── docs/
│   ├── agenten-issue-kommentar-template.md
│   ├── dokumentation-Berechtigungen geloest-dev-teamc1.md
│   ├── dokumentation-dev-team-pear.md
│   └── dokumentation-pear.md
├── README.md
├── images/
│   └── logo.png
├── modules/
│   ├── __init__.py
│   ├── requirements.txt
│   ├── run_agents.py
│   └── team.py
├── pear_email_ingest_mvp_imap/
│   ├── __pycache__/
│   ├── venv/
│   ├── .env
│   ├── Dockerfile
│   ├── imap_fetcher.py
│   ├── main.py
│   ├── README.md
│   ├── requirements.txt
│   └── schema.sql
├── pear_main/
├── pear-backend/
│   ├── __pycache__/
│   │   └── backend_app.cpython-311.pyc
│   ├── backend_app.py
│   ├── Dockerfile.function
│   ├── requirements.txt
│   ├── pear-email-processor-function/
│   ├── pear-frontend/
│   ├── scripts/
│   │   ├── backupagent_demo.py
│   │   └── dev_team_cloudbuild.yaml
│   ├── .env
│   ├── .gcloudignore
│   ├── .gitignore
│   ├── agents.md
│   ├── backend_agent_demo.py
│   ├── close_completed_issues.py
│   ├── cloudbuild.yaml
│   ├── cloudia_fastapi.py
│   ├── create_issues.py
│   ├── dev_team_cloudbuild.yaml
│   ├── Dockerfile
│   ├── label_all_completed_except_67.py
│   ├── README.md
│   ├── run_agents.ps1
│   ├── run_team.py
│   └── test_cloudia_gcp.py
└── _archive/
📅 Aktuelle Version
Stand: 11. August 2025