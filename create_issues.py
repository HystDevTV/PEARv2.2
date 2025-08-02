"""
create_issues.py – Erstellt Aufgaben als GitHub-Issues und weist sie optional Agenten zu.

Voraussetzungen:
- python-dotenv und PyGithub müssen installiert sein (siehe requirements.txt)
- GITHUB_TOKEN muss als Umgebungsvariable oder in einer .env-Datei gesetzt sein

Nutzung:
- Aufgaben als Liste im Skript eintragen (title, body, labels)
- Skript ausführen: python create_issues.py
"""

import os
from github import Github
from dotenv import load_dotenv

load_dotenv()

github_token = os.environ.get("GITHUB_TOKEN")
repo_name = "HystDevTV/PEARv2"  # ggf. anpassen


# Aufgaben als große Masterbeschreibung (A./B./C. und 1./2./3. Format)
MASTER_TASK_TEXT = """
A. QA/Testing-Spezialist
1. Cloud Build Trigger der PEARv2-VM testen (Build, Push, Deploy, Log-Bucket prüfen)
2. Prüfen, ob die Authorisierungsprobleme (wie in PEAR-DEV-TeamV1 gelöst) auch in PEARv2 auftreten und ggf. die Lösung übertragen
3. Automatisierte Tests für neue Features schreiben und in die CI/CD-Pipeline integrieren

B. Data/AI Engineer
1. Datenbank der PEARv2-VM prüfen: Struktur, Integrität, Performance
2. Datenbank ggf. erweitern (z.B. neue Tabellen/Spalten für neue Features)
3. Backup- und Restore-Strategie für die Datenbank dokumentieren und testen

C. Backend-Entwickler
1. Firebase-Authentifizierung ins Backend einbauen (Registrierung, Login, Token-Handling)
2. Python-Code für Authentifizierung und User-Management schreiben
3. API-Endpunkte für Authentifizierung und User-Profile implementieren

D. Dokumentations-Agent
1. Alle neuen Schritte und Änderungen in der dokumentation-pear.md dokumentieren
2. Neue Einträge mit aktuellem Datum und Kommentar „[NEU am <Datum>]“ kennzeichnen
3. Kurze Zusammenfassungen der Änderungen/Erkenntnisse für Neueinsteiger ergänzen
4. Automatische Secrets-Verwaltung via Secret Manager
5. Mehrere Docker Images parallel bauen (Matrix-Strategie)
6. Web-UI für Deployments (internes Dashboard)
"""

# Mapping von Topic zu Label
TOPIC_TO_LABEL = {
    'QA/Testing-Spezialist': 'Qualitätssicherung',
    'Data/AI Engineer': 'E-Mail- & KI-Verarbeitung',
    'Backend-Entwickler': 'API & Datenbank',
    'Backend Entwickler': 'API & Datenbank',
    'Dokumentations-Agent': 'Dokumentation',
    'DevOps-Engineer': 'Deployment & Infrastruktur',
    'DevOps Engineer': 'Deployment & Infrastruktur',
    'Frontend-Entwickler': 'UI & UX',
    'Frontend Entwickler': 'UI & UX',
    'Projektmanager': 'Koordination',
}

import re

def parse_master_tasks(text):
    tasks = []
    current_topic = None
    topic_regex = re.compile(r"^([A-Z])\.\s+([\w\-/ ]+)", re.UNICODE)
    task_regex = re.compile(r"^(\d+)\.\s+(.*)")
    for line in text.splitlines():
        topic_match = topic_regex.match(line.strip())
        if topic_match:
            current_topic = topic_match.group(2).strip()
            continue
        task_match = task_regex.match(line.strip())
        if task_match and current_topic:
            task_text = task_match.group(2).strip()
            label = TOPIC_TO_LABEL.get(current_topic, current_topic)
            tasks.append({
                "title": task_text,
                "body": f"{current_topic}: {task_text}",
                "labels": [label]
            })
    return tasks

TASKS = parse_master_tasks(MASTER_TASK_TEXT)

def main():
    if not github_token:
        print("Fehler: GITHUB_TOKEN nicht gesetzt.")
        return
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    for task in TASKS:
        issue = repo.create_issue(
            title=task["title"],
            body=task["body"],
            labels=task.get("labels", [])
        )
        print(f"Issue erstellt: #{issue.number} – {issue.title}")

if __name__ == "__main__":
    main()
