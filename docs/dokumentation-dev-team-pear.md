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

## 📘 Aufgabenverteilung über GitHub-Issues

Um eine automatisierte Bearbeitung durch den Projektleiter (PL) und die KI-Agenten zu ermöglichen, müssen Aufgaben als GitHub-Issues** verfasst werden dies können auch mehrere Tasks für verschiedene Agenten in einem Issue verfasst werden. Wichtig ist dabei folgende Formatierung:

## Anleitung: Aufgabenverteilung über ein zentrales Master-Ticket
Um die Arbeit für das Team zu organisieren, verwenden wir ein zentrales "Master-Ticket" auf GitHub. Das Agenten-System liest den Inhalt (Body) dieses einen Tickets und verteilt alle darin enthaltenen Aufgaben automatisch an die zuständigen Spezialisten.

## Das Grundprinzip
Der Titel des Tickets ist für uns Menschen. Die Maschine interessiert sich nur für den Inhalt des Tickets. Jede Aufgabe muss dort in einem speziellen Format auf einer eigenen Zeile stehen.

Die magische Formel lautet: [Rolle des Agenten]: Genaue Beschreibung der Aufgabe

Schritt 1: Das Master-Ticket erstellen
Gehen Sie zum GitHub-Repository HystDevTV/PEARv2.2.

Klicken Sie auf den Tab "Issues".

Klicken Sie auf den grünen Button "New issue".

Geben Sie dem Issue einen Titel, der für Menschen verständlich ist, z.B.:

Heutige Aufgaben 07.08.2025

Aufgaben für Sprint-Woche 32

Offene Punkte für Feature X

Schritt 2: Aufgaben im Ticket-Inhalt formatieren (Der wichtigste Schritt!)
Kopieren Sie die folgenden Aufgaben-Beispiele in das große Textfeld ("Leave a comment") und passen Sie sie an Ihre Bedürfnisse an.

Wichtig: Jede Aufgabe muss auf einer neuen Zeile stehen und mit einer der folgenden Rollen beginnen:

Um diesen Agenten zu beauftragen:	Verwenden Sie diese Rolle:
Backend-Entwickler	[API & Datenbank]
DevOps-Engineer	[Deployment & Infrastruktur]
Dokumentations-Agent	[Dokumentation]
CloudIA	[Cloud & GCP-Expertin]
Frontend-Entwickler	[UI & UX]
Projektmanager	[Koordination]


Beispiel für den Ticket-Inhalt:
Markdown

Hallo Team,

hier sind die Aufgaben für heute:

[API & Datenbank]: Den neuen Endpunkt /api/clients für die Kundenliste implementieren.
[Deployment & Infrastruktur]: Die neue Version des Agenten-Systems automatisch auf Cloud Run deployen.
[Dokumentation]: Die Anleitung für das Issue-Format fertigstellen und in die README aufnehmen.
[UI & UX]: Die Ladeanimation auf der Login-Seite einfügen.
[Cloud & GCP-Expertin]: Ein Konzept für die automatische Skalierung der Datenbank erstellen.

Danke & let's ship it! 🚀
Schritt 3: Ticket speichern und System starten
Klicken Sie auf "Submit new issue", um das Master-Ticket zu speichern.

Stellen Sie sicher, dass das Ticket kein completed-by-agent Label hat.

Führen Sie das run_agents.py-Skript aus.

Das System wird das Ticket finden, die 5 Aufgaben aus dem Inhalt lesen und sie an die richtigen 5 Agenten verteilen.

### 🔄 Vorgehensweise für den Projektleiter

1. **Jede Teilaufgabe** (z. B. aus einem Master-Issue mit Checkliste) wird in ein eigenes GitHub-Issue nach obigem Format übertragen.
2. Die **Kategorie** bestimmt automatisch den zuständigen Agenten.
3. Die Agenten erhalten ihre Aufgaben beim Start über `TaskManager.assign_tasks()`.
4. Die Bearbeitung erfolgt durch `agent.execute_task(...)`.
5. Nach erfolgreichem Abschluss wird das Issue automatisch:
   - kommentiert
   - mit `completed-by-agent` gelabelt

---

### ⛔ Hinweise
| Punkt | Bedeutung |
|-------|-----------|
| **Kategorie** | Muss exakt mit einer Agentenrolle in `team.py` übereinstimmen. |
| **Keine Checkboxes** | Nur echte Einzel-Issues im beschriebenen Format werden verarbeitet. |
| **Label** | `completed-by-agent` wird vom System gesetzt. Nur Issues **ohne dieses Label** werden verteilt. |

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

  7. 🚀 Inbetriebnahme des Agenten-Systems (07.08.2025)
Dieser Abschnitt dokumentiert den Weg von den ersten Code-Anpassungen bis zum voll funktionsfähigen Prototyp des PEAR-Dev-TeamV1-Moduls. Er dient als Blaupause, um den Prozess bei Bedarf nachzuvollziehen.

7.1. 🎯 Phase 1: Die Ausgangslage – Refactoring der Code-Basis
Der Prozess begann mit einem umfassenden Refactoring der Skripte run_agents.py und team.py, um eine saubere und wartbare Architektur zu schaffen (NF-WF-001).

Ziel: Klare Trennung der Verantwortlichkeiten.

team.py: Definiert die Agenten, ihre Fähigkeiten und die zentrale Logik zur Aufgabenverwaltung (TaskManager).

run_agents.py: Dient ausschließlich als Orchestrator, der die Threads startet und den Gesamtprozess steuert.

Sicherheitsverbesserung: Die DatabaseConnector-Klasse wurde so angepasst, dass sie Datenbank-Zugangsdaten zwingend aus Umgebungsvariablen (.env-Datei) erwartet, um das Hardcoding von Passwörtern zu vermeiden.

7.2. 🛠️ Phase 2: Die Debugging-Reise – Fehleranalyse und Lösungsfindung
Bei der Inbetriebnahme traten mehrere, aufeinanderfolgende Fehler auf, die systematisch identifiziert und gelöst wurden.

AttributeError & SyntaxError
🔴 Problem: Methoden-Umbenennungen aus dem Refactoring wurden nicht überall übernommen. Zusätzlich wurde versehentlich Text aus der Konversation in die .py-Dateien kopiert, was zu ungültigem Python-Code führte.

🟢 Lösung: Vereinheitlichung aller Methodenaufrufe und sorgfältige Bereinigung der Skript-Dateien.

GitHub API Error: 404 Not Found
🔴 Problem: Das Skript suchte im falschen Repository (HystDevTV/PEARv2) nach Aufgaben.

🟢 Lösung: Korrektur des hartcodierten Repository-Namens auf HystDevTV/PEARv2.2 an allen relevanten Stellen in team.py.

Fehlerhafte Aufgaben-Zuweisung
🔴 Problem: Eine zu stark vereinfachte Logik analysierte nur noch den Issue-Titel. Die Anforderung, alle Aufgaben aus dem Inhalt eines einzigen Master-Tickets zu lesen, wurde nicht erfüllt.

🟢 Lösung: Komplette Überarbeitung der assign_tasks-Methode. Sie analysiert nun den Body eines Issues und nutzt eine robuste Normalisierungsfunktion, um auch Rollen mit Sonderzeichen (&, -) sicher zu erkennen.

IndentationError
🔴 Problem: Eine neu eingeführte, verschachtelte Hilfsfunktion war beim Kopieren falsch eingerückt worden, was zu einem Syntaxfehler führte.

🟢 Lösung: Korrektur der Einrückungen, um die Python-Syntax zu erfüllen und die Lesbarkeit zu verbessern.



7.3. ✨ Phase 3: Meilenstein – Der funktionale Prototyp ist LIVE!
Nach einem intensiven Debugging-Zyklus wurde ein erfolgreicher End-to-End-Test durchgeführt, der die volle Funktionsfähigkeit des Systems bestätigt.

✅ Intelligente Aufgabenverteilung: Alle Teilaufgaben aus dem Master-Ticket wurden fehlerfrei erkannt und den korrekten Spezialisten-Agenten zugewiesen.

✅ Echte Fähigkeiten: Die Agenten sind aus dem Dummy-Modus erwacht und haben erfolgreich reale Datei-Schreiboperationen durchgeführt.

✅ Parallele Abarbeitung: Alle Agenten haben gleichzeitig und ohne Konflikte gearbeitet.

.

✅ End-to-End-Funktionalität: Der gesamte Workflow – von der Aufgabenstellung in einem GitHub-Issue über die Ausführung bis zum greifbaren Ergebnis – funktioniert nahtlos.

Das PEAR-Dev-TeamV1-System hat damit den Status eines funktionalen Prototyps erreicht.