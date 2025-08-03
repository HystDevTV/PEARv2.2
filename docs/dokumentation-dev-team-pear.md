# Projektdokumentation Dev-Team-PEAR (Unterprojekt von PEAR)

**Stand:** 22. Juli 2025

---

## 1. Zielsetzung

Das Ziel von **Dev-Team-PEAR** ist es, ein System zu schaffen, in dem verschiedene Teamrollen (Agenten) ihre Aufgaben automatisiert und parallel abarbeiten können.  
Der Projektmanager (Projektleiter) soll dabei automatisch für alle Aufgaben der Teammitglieder GitHub-Issues anlegen.

---

## 2. Projektstruktur

### 2.1. Team-Definition (`modules/team.py`)

- **Agenten** werden als Python-Datenklassen definiert.
- Jede Rolle (z. B. Projektmanager, Backend-Entwickler, DevOps-Engineer) hat:
  - Einen Namen
  - Eine Rolle
  - Eine Aufgabenliste (`tasks`)
  - Eine Hintergrundbeschreibung (`backstory`)
- Die Funktion `build_team()` erzeugt das komplette Team mit allen Aufgaben.

### 2.2. Automatisierungsskript (`modules/run_agents.py` oder `run_agents.py`)

- Importiert das Team aus `team.py`.
- Für jeden Agenten wird ein eigener Thread (Worker) gestartet.
- **Projektmanager:**  
  - Erkennt seine Rolle (`role == "Koordination"`).
  - Legt für jede Aufgabe der anderen Agenten automatisch ein GitHub-Issue an (über die GitHub-API).
- **Alle anderen Agenten:**  
  - Arbeiten ihre Aufgaben simuliert ab (Ausgabe im Terminal).

---

## 3. GitHub-Issue-Automatisierung

- Die Funktion `create_github_issue(title, body)` erstellt Issues im angegebenen GitHub-Repo.
- Der Zugriff erfolgt über ein persönliches Zugriffstoken (`GITHUB_TOKEN`), das als Umgebungsvariable gesetzt sein muss.
- Die Issues werden mit Titel und Beschreibung automatisch angelegt.

---

## 4. Ausführung

1. **Voraussetzungen:**
   - Python-Umgebung
   - Gültiges GitHub-Token als Umgebungsvariable `GITHUB_TOKEN`
   - Korrekte Repo-Angabe in `run_agents.py`
   - **Für Cloud Build/Cloud Run:**  
     - Docker-Image wird nach `gcr.io/pear-dev-teamv1/dev-team-pear-agenten` gebaut und gepusht

2. **Starten:**
   ```sh
   python run_agents.py
   ```
   oder
   ```sh
   python modules/run_agents.py
   ```
   oder als Docker-Container:
   ```sh
   docker run --env GITHUB_TOKEN=dein_token gcr.io/pear-dev-teamv1/dev-team-pear-agenten
   ```
   
---

## 5. Erweiterungsmöglichkeiten

- Automatisierte Code-Generierung für Backend-Logik (z. B. FastAPI-Endpunkte)
- Automatisierte Cloud-Konfiguration (z. B. GCP, Terraform)
- Integration von KI-Services (z. B. OpenAI für Text- oder Code-Generierung)
- Fortschritts-Tracking und Rückmeldung aus GitHub-Issues

---

## 6. Best Practices

- **Trennung von Logik:**  
  Team-Definition (`team.py`) und Automatisierung/Ausführung (`run_agents.py`) sind sauber getrennt.
- **Dokumentation:**  
  Projektdokumentation liegt als Markdown im Repo (`/docs/dokumentation-dev-team-pear.md`).
- **Nachvollziehbarkeit:**  
  Alle automatisierten Schritte werden im Terminal ausgegeben und sind im GitHub-Issue-Tracker sichtbar.

---

**Status:**  
Automatisierte Aufgabenverteilung und Issue-Erstellung durch den Projektmanager erfolgreich umgesetzt.  
**Nächste Schritte:** Weitere Automatisierung der Agenten-Aufgaben (z. B. Code-Generierung, Cloud-Setup).

# 📘 Projektdokumentation: PEARv2.2 Agenten-Taskmanagement

## 📌 Ziel
Ein intelligentes Multi-Agenten-System zur automatisierten Abarbeitung von GitHub-Issues durch spezialisierte Agenten. Der Projektleiter (PL) analysiert zentrale Aufgaben-Issues, verteilt Aufgaben automatisch an zuständige Teammitglieder, und jeder Agent dokumentiert seinen Fortschritt in Echtzeit.

## 🧱 Architekturüberblick

```txt
PEARv2.2/
│
├── modules/
│   ├── team.py            # Enthält Agentendefinitionen, TaskManager und Logik zur Teamerstellung
│   ├── run_agents.py      # Steuerungsskript: Ruft Issues ab, verteilt Aufgaben, startet Agentenausführung
│
├── create_issues.py       # Optionales Skript zum automatischen Anlegen von GitHub-Issues
├── .env                   # Enthält GITHUB_TOKEN zur Authentifizierung der GitHub-API
├── requirements.txt       # (z. B.) PyGithub, python-dotenv, etc.
```

## ⚙️ Setup

### 1. `.env`-Datei erstellen:
```env
GITHUB_TOKEN=ghp_deinTokenHierEinfügen
```

### 2. Notwendige Abhängigkeiten installieren:
```bash
pip install PyGithub python-dotenv
```

## 👥 Agentenstruktur

Jeder Agent ist eine Instanz der `Agent`-Klasse. Die Rollen sind z. B.:
- Projektmanager (Koordination)
- Backend-Entwickler (API & Datenbank)
- Frontend-Entwickler (UI & UX)
- CloudIA (Cloud & GCP-Expertin)
- QA/Testing-Spezialist
- uvm.

Die Agenten werden in `build_team()` in `team.py` initialisiert.

## 🔄 TaskManager: Aufgabenlogik

### Klasse: `TaskManager`
Verantwortlich für:
- Abrufen offener GitHub-Issues
- Extrahieren und Zuweisen der Aufgaben (basierend auf Rollenschlüsselwörtern)
- Reporting nach Abarbeitung

```python
manager = TaskManager(team)
manager.fetch_github_issues()
manager.assign_tasks()
```

### 📥 `fetch_github_issues()`
- Holt alle offenen Issues aus dem GitHub-Repo
- Filtert jene ohne das Label `completed-by-agent`

### 🧠 `assign_tasks()`
- Verarbeitet `body` der Issues (Markdown-Format)
- Extrahiert Aufgaben & Kategorie mit `extract_tasks_from_issue_body()`
- Weist Aufgaben passenden Agenten zu

## 🧪 Beispiel-Aufgaben-Format in GitHub-Issues:

```md
## Aufgabenliste für den Sprint:

- [Backend] Neue API-Endpunkte für Nutzerstatistik
- [Frontend] Verbesserte UI für Dashboard
- [Cloud] Deployment auf Cloud Run automatisieren
```

## 🚀 Ablauf (`run_agents.py`)

```python
team = build_team()
manager = TaskManager(team)
manager.fetch_github_issues()
manager.assign_tasks()
```

- PL analysiert zentrale Issues, extrahiert Aufgaben, verteilt via `create_github_issue()`
- Alle Agenten rufen ihre `tasks` ab und führen sie aus via `agent.execute_task()`
- Ergebnisse werden geloggt und ggf. kommentiert oder mit Labels versehen

## 📊 Reporting

### 🧾 Beispielausgabe nach erfolgreicher Ausführung:

```txt
2025-08-03 02:07:27,980 - INFO - Projektmanager: 1 Aufgaben zugewiesen, 1 erledigt.
2025-08-03 02:07:27,981 - INFO - Backend-Entwickler: 1 Aufgaben zugewiesen, 1 erledigt.
...
```

## 🧼 Fehlerquellen & Tipps

- 🔐 **Token nicht gesetzt**: `.env` vergessen?
- 🧠 **Keine Aufgaben erkannt**: Format der Aufgabenliste prüfen
- 🕳️ **Agent hat keine passende Rolle**: Kategorie stimmt nicht mit Agentenrolle überein
- 🔄 **Kein Output?** Logging-Level prüfen oder `agent.report()` fehlt

## ✅ Status

| Komponente           | Implementiert | Getestet |
|----------------------|---------------|----------|
| Agentenmodellierung      | ✅            | ✅       |
| GitHub-Issue-Import      | ✅            | ✅       |
| Automatisierte Zuweisung | ✅            | ✅       |
| Abarbeitung durch Agents | ✅            | ✅       |
| Rückmeldung an GitHub    | 🔜     | 🔜       |
  (Label + Kommentar)