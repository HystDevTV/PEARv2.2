import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import mysql.connector
from dotenv import load_dotenv
from github import Github, GithubException
from mysql.connector import Error

# Lädt Umgebungsvariablen aus der .env-Datei
load_dotenv()

# Konfiguriert ein zentrales Logging-System
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
)
logger = logging.getLogger("PEAR-Team-Module")


class DatabaseConnector:
    """Stellt eine sichere Verbindung zur MySQL-Datenbank her und verwaltet diese."""

    def __init__(self):
        """Initialisiert den Connector und prüft auf das Vorhandensein aller DB-Secrets."""
        self.host = os.environ.get("DB_HOST")
        self.user = os.environ.get("DB_USER")
        self.password = os.environ.get("DB_PASSWORD")
        self.database = os.environ.get("DB_NAME")
        self.connection = None

        if not all([self.host, self.user, self.password, self.database]):
            # Stoppt die Ausführung, wenn Konfiguration unvollständig ist
            # Dies ist ein Fail-Fast-Ansatz, um Laufzeitfehler zu vermeiden
            raise ValueError(
                "DB_HOST, DB_USER, DB_PASSWORD und DB_NAME müssen als Umgebungsvariablen gesetzt sein."
            )

    def connect(self) -> bool:
        """Baut die Datenbankverbindung auf."""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                autocommit=True, # Stellt sicher, dass jeder Befehl sofort ausgeführt wird
            )
            logger.info("Datenbankverbindung erfolgreich hergestellt.")
            return True
        except Error as e:
            logger.error(f"Datenbankverbindung fehlgeschlagen: {e}")
            return False

    def close(self):
        """Schließt die Datenbankverbindung, falls sie offen ist."""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("Datenbankverbindung sicher geschlossen.")

    # Weitere Methoden wie create_tables, store_agent etc. bleiben hier unverändert...


@dataclass
class Agent:
    """Definiert einen Agenten mit seinen Fähigkeiten, Aufgaben und seiner Rolle im Team."""

    name: str
    role: str
    backstory: str = ""
    tasks: List[dict] = field(default_factory=list, repr=False)
    completed_tasks: List[dict] = field(default_factory=list, repr=False)
    db_connector: Optional[DatabaseConnector] = field(default=None, repr=False)
    db_agent_id: Optional[int] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Wird nach der Initialisierung des Agenten aufgerufen, um ihn in der DB zu registrieren."""
        if self.db_connector:
            # Hier würde die Logik zum Speichern/Aktualisieren des Agenten in der DB stehen
            # self.db_agent_id = self.db_connector.store_agent(...)
            logger.info(f"Agent {self.name} initialisiert.")

    def execute_all_tasks(self) -> None:
        """Führt alle dem Agenten zugewiesenen Aufgaben nacheinander aus."""
        logger.info(f"{self.name} startet mit der Abarbeitung von {len(self.tasks)} Aufgabe(n).")
        for task in self.tasks:
            self.execute_task(task)
        self.tasks.clear()

    def execute_task(self, task_details: dict):
        """Führt eine einzelne Aufgabe aus und dokumentiert das Ergebnis."""
        title = task_details.get("title", "Unbenannte Aufgabe")
        issue_number = task_details.get("issue_number")
        logger.info(f"{self.name} beginnt mit der Aufgabe: '{title}' (Issue #{issue_number})")

        # Die eigentliche Arbeit wird hier basierend auf der Rolle ausgeführt
        result_message = self._process_task_by_role(task_details)

        self.completed_tasks.append(task_details)
        logger.info(f"{self.name} hat die Aufgabe abgeschlossen: '{title}'")

        # Nach Abschluss wird das GitHub-Issue aktualisiert
        if issue_number:
            self._update_github_issue(issue_number, result_message)

    # Dieser Code kommt in die Agent-Klasse in team.py

    def _process_task_by_role(self, task_details: dict) -> str:
        """
        Verarbeitet eine Aufgabe basierend auf der Agentenrolle und dem Aufgabentitel.
        Implementiert jetzt die Fähigkeit, Skill-Dateien zu erstellen.
        """
        title = task_details["title"]
        
        # Prüfen, ob es sich um die neue Skill-Aufgabe handelt
        if "markdown-datei" in title.lower() and "fähigkeiten" in title.lower():
            try:
                # Zielverzeichnis definieren und erstellen, falls es nicht existiert
                # Geht vom 'modules'-Ordner eine Ebene hoch und dann in 'docs/agent_skills'
                output_dir = os.path.join(os.path.dirname(__file__), '..', 'docs', 'agent_skills')
                os.makedirs(output_dir, exist_ok=True)
                
                # Dateinamen aus der Rolle des Agenten ableiten
                filename_role = self.role.lower().replace(' & ', '_und_').replace(' ', '_').replace('/', '_')
                filepath = os.path.join(output_dir, f"{filename_role}.md")

                # Inhalt für die Markdown-Datei erstellen
                content = (
                    f"# Steckbrief: {self.name}\n\n"
                    f"**Rolle:** {self.role}\n\n"
                    f"## Hintergrund & Fähigkeiten\n\n"
                    f"{self.backstory}\n"
                )
                
                # Datei schreiben
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                
                logger.info(f"{self.name} hat die Skill-Datei erfolgreich unter '{filepath}' erstellt.")
                return f"Skill-Datei erfolgreich unter '{filepath}' erstellt."

            except Exception as e:
                logger.error(f"Fehler beim Erstellen der Skill-Datei für {self.name}: {e}")
                return f"Konnte Skill-Datei nicht erstellen: {e}"
            else:
                # Fallback auf die bisherige Sleep-Funktion für alle anderen Aufgaben
                logger.info(f"{self.name} führt eine generische Aufgabe aus: '{title}'...")
                time.sleep(1)
                return f"Die generische Aufgabe '{title}' wurde simuliert."

    def _update_github_issue(self, issue_number: int, result: str):
        """Fügt einen Kommentar zum GitHub-Issue hinzu und schließt es für Agenten."""
        try:
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                logger.warning(
                    f"Kein GITHUB_TOKEN gefunden. Update für Issue #{issue_number} übersprungen."
                )
                return

            g = Github(token)
            repo = g.get_repo("HystDevTV/PEARv2.2")  # Repo-Name zentralisiert
            issue = repo.get_issue(number=issue_number)

            # Kommentar erstellen basierend auf dem Template
            comment_body = (
                f"## Aufgabe abgeschlossen von {self.name}\n\n"
                f"**Status:** erledigt\n\n"
                f"**Nachricht:** {result}\n\n"
                f"**Datum:** {datetime.now().strftime('%d.%m.%Y, %H:%M:%S Uhr')}\n\n"
                ""
            )

            issue.create_comment(comment_body)
            issue.add_to_labels("completed-by-agent")
            logger.info(f"GitHub Issue #{issue_number} erfolgreich kommentiert und gelabelt.")

        except GithubException as e:
            logger.error(
                f"GitHub API Fehler beim Update von Issue #{issue_number}: {e.status} {e.data}"
            )
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Issue-Update: {e}")


class TaskManager:
    """Holt, analysiert und verteilt Aufgaben aus GitHub-Issues an das Agenten-Team."""

    def __init__(self, agents: List[Agent], db_connector: Optional[DatabaseConnector] = None):
        """Initialisiert den TaskManager mit dem Team."""
        self.agents = agents
        self.db_connector = db_connector
        self.issues = []
        self.role_to_agent = {agent.role: agent for agent in self.agents}

    def fetch_github_issues(self):
        """Holt alle offenen Issues, die noch nicht von einem Agenten bearbeitet wurden."""
        logger.info("Starte Abruf von offenen GitHub Issues...")
        try:
            repo_name = os.getenv("GITHUB_REPO", "HystDevTV/PEARv2.2")
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                raise ValueError("GITHUB_TOKEN nicht gefunden.")

            g = Github(token)
            repo = g.get_repo(repo_name)
            open_issues = repo.get_issues(state="open")

            self.issues = []
            for issue in open_issues:
                labels = [label.name for label in issue.labels]
                if "completed-by-agent" not in labels:
                    self.issues.append(
                        {
                            "number": issue.number,
                            "title": issue.title,
                            "body": issue.body,
                        }
                    )
            logger.info(
                f"{len(self.issues)} relevante, offene Issue(s) gefunden."
            )
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der GitHub Issues: {e}")
            self.issues = []

    def assign_tasks(self):
   # """
    #Verteilt Aufgaben, indem der Inhalt (Body) von Master-Tickets analysiert wird.
    #Diese Version nutzt eine normalisierte Prüfung, um auch Rollen mit Sonderzeichen
    #sicher zu erkennen.
    
        logger.info("Beginne mit der Aufgabenverteilung aus Issue-Inhalten...")
        for agent in self.agents:
            agent.tasks.clear()
            agent.completed_tasks.clear()

        task_pattern = re.compile(r"\[(.+?)\]:\s*(.+)")

        def _normalize_role(text: str) -> str:
            """Eine interne Hilfsfunktion, um Rollen für den Vergleich zu bereinigen."""
            return text.lower().replace('&', '').replace('-', '').replace(' ', '')

        for issue in self.issues:
            tasks_found_in_body = 0
            for line in issue["body"].splitlines():
                match = task_pattern.match(line.strip())
                if match:
                    role_key, task_title = match.groups()
                    normalized_role_key = _normalize_role(role_key)
                    assigned = False

                    for agent in self.agents:
                        # Normalisiere die Agenten-Rolle und vergleiche sie exakt
                        if _normalize_role(agent.role) == normalized_role_key:
                            task_details = {
                                "title": task_title.strip(),
                                "description": f"Teilaufgabe aus Issue #{issue['number']}: {issue['title']}",
                                "issue_number": issue["number"],
                                "category": agent.role,
                            }
                            agent.tasks.append(task_details)
                            assigned = True
                            tasks_found_in_body += 1
                            logger.info(f"Teilaufgabe '{task_title}' an {agent.name} zugewiesen.")
                            break
            
            if tasks_found_in_body > 0:
                # Nach der Zuweisung aller Teilaufgaben, markiere das Master-Ticket, damit es nicht erneut bearbeitet wird
                logger.info(f"{tasks_found_in_body} Teilaufgaben aus Issue #{issue['number']} zugewiesen.")
                # Hier könnte man das Master-Ticket direkt kommentieren oder labeln,
                # aber wir lassen das die Agenten für ihre jeweiligen Teilaufgaben machen.
                pass
            else:
                pm_agent = self.role_to_agent.get("Koordination")
                if pm_agent:
                    task_details = {
                        "title": f"Master-Ticket ohne erkennbare Aufgaben analysieren: '{issue['title']}'",
                        "description": issue["body"],
                        "issue_number": issue["number"],
                        "category": "Koordination",
                    }
                    pm_agent.tasks.append(task_details)
                    logger.warning(
                        f"Keine Teilaufgaben im Body von Issue #{issue['number']} gefunden. Gesamtes Issue an Projektmanager übergeben."
                    )
        logger.info("Aufgabenverteilung abgeschlossen.")

    def print_status(self, final: bool = False):
        """Gibt einen formatierten Statusbericht über die Agenten und ihre Aufgaben aus."""
        status_header = "=== ABSCHLUSSBERICHT ===" if final else "=== AKTUELLER AUFGABENSTATUS ==="
        print(f"\n{status_header}")

        for agent in self.agents:
            tasks_total = len(agent.tasks) + len(agent.completed_tasks)
            tasks_done = len(agent.completed_tasks)
            status_icon = "✅" if tasks_total == tasks_done and tasks_total > 0 else "🔄"
            if tasks_total == 0: status_icon = "🤷"
            
            print(
                f"{status_icon} {agent.name} ({agent.role}): {tasks_done}/{tasks_total} Aufgaben abgeschlossen."
            )
        print("=" * len(status_header))

def build_team(db_connector: Optional[DatabaseConnector] = None) -> List[Agent]:
    """Erstellt das Team von Agenten, wie in der Dokumentation definiert."""
    # Die Definitionen der Agenten bleiben hier unverändert...
    return [
        Agent(
            name="Projektmanager",
            role="Koordination",
            backstory="Koordiniert alle Teams und analysiert unklare Aufgaben.",
            db_connector=db_connector,
        ),
        Agent(
            name="Backend-Entwickler",
            role="API & Datenbank",
            backstory="Entwickelt Python-basierte APIs und managt Datenbanken.",
            db_connector=db_connector,
        ),
        Agent(
            name="Frontend-Entwickler",
            role="UI & UX",
            backstory="Erstellt moderne und benutzerfreundliche Weboberflächen.",
            db_connector=db_connector,
        ),
        Agent(
            name="DevOps-Engineer",
            role="Deployment & Infrastruktur",
            backstory="Automatisiert Deployments und managt die Cloud-Infrastruktur.",
            db_connector=db_connector,
        ),
        Agent(
            name="QA/Testing-Spezialist",
            role="Qualitätssicherung",
            backstory="Spezialist für Testautomatisierung und CI/CD-Pipelines.",
            db_connector=db_connector,
        ),
        Agent(
            name="Dokumentations-Agent",
            role="Dokumentation",
            backstory="Schreibt präzise und verständliche Dokumentationen.",
            db_connector=db_connector,
        ),
        Agent(
            name="CloudIA",
            role="Cloud & GCP-Expertin",
            backstory="Expertin für die Entwicklung, Implementierung und Optimierung von Lösungen auf der Google Cloud Platform.",
            db_connector=db_connector,
        ),
    ]