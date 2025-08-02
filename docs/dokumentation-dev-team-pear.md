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
