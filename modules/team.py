
import logging
from dotenv import load_dotenv
load_dotenv()
import mysql.connector
from mysql.connector import Error
import time
from dataclasses import dataclass, field
from typing import List, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PEAR-Team")

# TaskManager für dynamische Aufgabenverteilung und Reporting
class TaskManager:
    def __init__(self, agents: List['Agent'], db_connector: Optional['DatabaseConnector'] = None):
        self.agents = agents
        self.db_connector = db_connector
        self.issues = []

    def fetch_github_issues(self):
        import os
        from github import Github
        github_token = os.environ.get("GITHUB_TOKEN")
        if not github_token:
            logger.warning("Kein GitHub-Token verfügbar. Issue-Abruf übersprungen.")
            return []
        g = Github(github_token)
        repo = g.get_repo("HystDevTV/PEARv2")
        # Optional: Nur ein bestimmtes Issue verarbeiten, falls PEAR_ISSUE_NUMBER gesetzt ist
        issue_number = os.environ.get("PEAR_ISSUE_NUMBER")
        filtered_issues = []
        if issue_number:
            try:
                issue = repo.get_issue(int(issue_number))
                # Prüfe, ob offen und nicht erledigt
                labels = [label.name for label in getattr(issue, 'labels', [])]
                if (getattr(issue, 'state', 'open') == 'open') and ("completed-by-agent" not in labels) and not getattr(issue, 'pull_request', False):
                    filtered_issues.append(issue)
            except Exception as e:
                logger.error(f"Fehler beim Abrufen von Issue #{issue_number}: {e}")
        else:
            issues = repo.get_issues(state="open")
            for issue in issues:
                if getattr(issue, 'pull_request', False):
                    continue
                labels = [label.name for label in getattr(issue, 'labels', [])]
                if "completed-by-agent" not in labels and getattr(issue, 'state', 'open') == 'open':
                    filtered_issues.append(issue)
        self.issues = filtered_issues
        logger.info(f"{len(self.issues)} offene GitHub-Issues ohne 'completed-by-agent' abgerufen.")
        return self.issues

    def categorize_issue(self, issue):
        # Einfache Kategorisierung nach Label
        label_map = {
            "infrastructure": "Deployment & Infrastruktur",
            "feature": "API & Datenbank",
            "frontend": "UI & UX",
            "ai": "E-Mail- & KI-Verarbeitung",
            "qa": "Qualitätssicherung",
            "docs": "Dokumentation",
            "coordination": "Koordination"
        }
        for label in issue.labels:
            if label.name in label_map:
                return label_map[label.name]
        return "Koordination"

    def assign_tasks(self):
        # Vor der Aufgabenverteilung: Aufgabenlisten aller Agenten leeren!
        for agent in self.agents:
            agent.tasks.clear()
        # Nochmals: Nur Issues mit state='open' und ohne Label 'completed-by-agent' verarbeiten
        for issue in self.issues:
            if getattr(issue, 'state', 'open') != 'open':
                continue
            labels = [label.name for label in getattr(issue, 'labels', [])]
            if 'completed-by-agent' in labels:
                continue
            assigned = False
            # Rolle aus Label oder Titel/Body ableiten
            labels_lower = [l.lower() for l in labels]
            role_map = {
                'qualitätssicherung': 'Qualitätssicherung',
                'e-mail- & ki-verarbeitung': 'E-Mail- & KI-Verarbeitung',
                'api & datenbank': 'API & Datenbank',
                'dokumentation': 'Dokumentation',
                'deployment & infrastruktur': 'Deployment & Infrastruktur',
                'ui & ux': 'UI & UX',
                'koordination': 'Koordination',
            }
            # 1. Nach Label zuweisen
            for label in labels_lower:
                if label in role_map:
                    for agent in self.agents:
                        if agent.role.lower() == role_map[label].lower():
                            agent.tasks.append({
                                'title': issue.title,
                                'description': issue.body,
                                'issue_number': getattr(issue, 'number', None)
                            })
                            assigned = True
                            break
                    if assigned:
                        break
            # 2. Falls nicht zugewiesen: nach Rolle im Titel/Body suchen
            if not assigned:
                for agent in self.agents:
                    if agent.role.lower() in (issue.title or '').lower() or agent.role.lower() in (issue.body or '').lower():
                        agent.tasks.append({
                            'title': issue.title,
                            'description': issue.body,
                            'issue_number': getattr(issue, 'number', None)
                        })
                        assigned = True
                        break
            # 3. Fallback: an Projektmanager (PL, meist self.agents[0])
            if not assigned and self.agents:
                self.agents[0].tasks.append({
                    'title': issue.title,
                    'description': issue.body,
                    'issue_number': getattr(issue, 'number', None)
                })
        logger.info("Aufgaben dynamisch an Agenten verteilt.")

    def run(self):
        self.fetch_github_issues()
        self.assign_tasks()
        self.report()
        for agent in self.agents:
            agent.execute_all_tasks()
        self.report(final=True)

    def report(self, final=False):
        if not final:
            logger.info("--- Team-Status vor Abarbeitung ---")
        else:
            logger.info("--- Team-Status nach Abarbeitung ---")
        for agent in self.agents:
            logger.info(f"{agent.name} ({agent.role}): {len(agent.tasks)} Aufgaben zugewiesen, {len(agent.completed_tasks)} erledigt.")

class DatabaseConnector:
    def __init__(self):
        import os
        self.host = os.environ.get("DB_HOST", "127.0.0.1")
        self.user = os.environ.get("DB_USER", "pear_user")
        self.password = os.environ.get("DB_PASSWORD", "SecurePear2024!")
        self.database = os.environ.get("DB_NAME", "pear_db")
        self.connection = None

    def connect(self) -> bool:
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                autocommit=True
            )
            logger.info("Datenbankverbindung erfolgreich hergestellt")
            return True
        except Error as e:
            logger.error(f"Datenbankverbindung fehlgeschlagen: {str(e)}")
            return False

    def create_tables(self):
        if not self.connection:
            logger.error("Keine Datenbankverbindung vorhanden")
            return False
        cursor = self.connection.cursor()
        try:
            agent_table = """
            CREATE TABLE IF NOT EXISTS agents (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                role VARCHAR(50) NOT NULL,
                backstory TEXT,
                status VARCHAR(20) DEFAULT 'idle',
                tasks_completed INT DEFAULT 0,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            task_table = """
            CREATE TABLE IF NOT EXISTS tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(500) NOT NULL,
                description TEXT,
                category VARCHAR(50),
                priority INT DEFAULT 0,
                status VARCHAR(20) DEFAULT 'pending',
                agent_id INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP NULL,
                completed_at TIMESTAMP NULL,
                result_data TEXT,
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL
            )
            """
            cursor.execute(agent_table)
            cursor.execute(task_table)
            logger.info("Tabellen erfolgreich erstellt/überprüft")
            return True
        except Error as e:
            logger.error(f"Fehler beim Erstellen der Tabellen: {str(e)}")
            return False
        finally:
            cursor.close()

    def store_agent(self, name: str, role: str, backstory: str = "") -> Optional[int]:
        if not self.connection:
            return None
        cursor = self.connection.cursor()
        try:
            check_query = "SELECT id FROM agents WHERE name = %s"
            cursor.execute(check_query, (name,))
            result = cursor.fetchone()
            if result:
                agent_id = result[0]
                update_query = """UPDATE agents SET role = %s, backstory = %s, status = 'active', last_active = NOW() WHERE id = %s"""
                cursor.execute(update_query, (role, backstory, agent_id))
            else:
                insert_query = """INSERT INTO agents (name, role, backstory, status) VALUES (%s, %s, %s, 'active')"""
                cursor.execute(insert_query, (name, role, backstory))
                agent_id = cursor.lastrowid
            return agent_id
        except Error as e:
            logger.error(f"Fehler beim Speichern des Agenten {name}: {str(e)}")
            return None
        finally:
            cursor.close()

    def store_task(self, title: str, description: str = "", category: str = "", priority: int = 0, agent_id: Optional[int] = None) -> Optional[int]:
        if not self.connection:
            return None
        cursor = self.connection.cursor()
        try:
            query = """INSERT INTO tasks (title, description, category, priority, agent_id) VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(query, (title, description, category, priority, agent_id))
            task_id = cursor.lastrowid
            return task_id
        except Error as e:
            logger.error(f"Fehler beim Speichern der Aufgabe '{title}': {str(e)}")
            return None
        finally:
            cursor.close()

    def complete_task(self, task_id: int, agent_id: int, result_data: str = None) -> bool:
        if not self.connection:
            return False
        cursor = self.connection.cursor()
        try:
            query = """UPDATE tasks SET status = 'completed', completed_at = NOW(), result_data = %s WHERE id = %s AND agent_id = %s"""
            cursor.execute(query, (result_data, task_id, agent_id))
            agent_query = "UPDATE agents SET tasks_completed = tasks_completed + 1, last_active = NOW() WHERE id = %s"
            cursor.execute(agent_query, (agent_id,))
            return True
        except Error as e:
            logger.error(f"Fehler beim Abschließen der Aufgabe {task_id}: {str(e)}")
            return False
        finally:
            cursor.close()

    def close(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("Datenbankverbindung geschlossen")

@dataclass
class Agent:
    name: str
    role: str
    tasks: List[str] = field(default_factory=list)
    backstory: str = ""
    db_connector: Optional[DatabaseConnector] = field(default=None, repr=False)
    db_agent_id: Optional[int] = field(default=None, init=False, repr=False)
    completed_tasks: List[str] = field(default_factory=list, init=False, repr=False)
    task_issue_numbers: Optional[List[int]] = field(default=None, repr=False)

    def __post_init__(self):
        if self.db_connector:
            self.db_agent_id = self.db_connector.store_agent(self.name, self.role, self.backstory)
            logger.info(f"Agent {self.name} mit DB-ID {self.db_agent_id} registriert")

    def execute_task(self, task, category: str = "", priority: int = 0, issue_number: int = None) -> bool:
        # task ist jetzt ein dict mit title, description, issue_number
        title = task['title'] if isinstance(task, dict) else str(task)
        description = task.get('description', '') if isinstance(task, dict) else ''
        issue_number = task.get('issue_number', None) if isinstance(task, dict) else issue_number
        logger.info(f"{self.name} startet Aufgabe: {title}")
        task_id = None
        if self.db_connector and self.db_agent_id:
            task_id = self.db_connector.store_task(title, description, category, priority, self.db_agent_id)
        result = self._process_task_by_role(title)
        if self.db_connector and task_id and self.db_agent_id:
            self.db_connector.complete_task(task_id, self.db_agent_id, result)
        self.completed_tasks.append(title)
        logger.info(f"{self.name} hat Aufgabe abgeschlossen: {title}")
        # GitHub-Kommentar nach Abschluss
        if issue_number:
            self._update_github_issue(issue_number, result)
        return True

    def _update_github_issue(self, issue_number: int, result: str) -> None:
        import os
        from datetime import datetime
        try:
            github_token = os.environ.get("GITHUB_TOKEN")
            if not github_token:
                logger.warning("Kein GitHub-Token verfügbar. Issue-Update übersprungen.")
                return
            from github import Github
            g = Github(github_token)
            repo = g.get_repo("HystDevTV/PEARv2")
            issue = repo.get_issue(number=issue_number)
            comment = f"## Aufgabe abgeschlossen von {self.name}\n\n"
            comment += f"**Status**: erledigt\n\n"
            comment += f"**Nachricht**: {result}\n\n"
            comment += f"**Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            issue.create_comment(comment)
            issue.add_to_labels("completed-by-agent")
            logger.info(f"GitHub Issue #{issue_number} aktualisiert")
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des GitHub Issues: {str(e)}")

    def _process_task_by_role(self, task: str) -> str:
        processing_times = {
            "Koordination": 1,
            "API & Datenbank": 3,
            "UI & UX": 2,
            "Deployment & Infrastruktur": 2,
            "E-Mail- & KI-Verarbeitung": 3,
            "Qualitätssicherung": 2,
            "Dokumentation": 1
        }
        sleep_time = processing_times.get(self.role, 1)
        time.sleep(sleep_time)
        return f"Aufgabe '{task}' erfolgreich bearbeitet"

    def execute_all_tasks(self) -> None:
        logger.info(f"{self.name} führt {len(self.tasks)} Aufgaben aus")
        for i, task in enumerate(self.tasks, 1):
            self.execute_task(task, category=self.role, priority=len(self.tasks) - i + 1)

def build_team(db_connector: Optional[DatabaseConnector] = None) -> List[Agent]:
    return [
        Agent(
            name="Projektmanager",
            role="Koordination",
            backstory="Hat jahrelange Erfahrung in agilen Projekten und koordiniert alle Teams.\n\nStammaufgabe: Für die Verteilung neuer Aufgaben im Team den Befehl 'python create_issues.py' ausführen, um Issues im GitHub-Repo automatisiert anzulegen.",
            db_connector=db_connector
        ),
        Agent(
            name="Backend-Entwickler",
            role="API & Datenbank",
            backstory="Entwickelt seit Jahren Python-basierte APIs und kennt sich bestens mit Datenbanken aus.",
            db_connector=db_connector
        ),
        Agent(
            name="Frontend-Entwickler",
            role="UI & UX",
            backstory="Bringt ein Auge für Design und Benutzerfreundlichkeit mit und erstellt moderne Weboberflächen.",
            db_connector=db_connector
        ),
        Agent(
            name="DevOps-Engineer",
            role="Deployment & Infrastruktur",
            backstory="Automatisierungsexperte, sorgt für reibungslose Deployments in der Cloud.",
            db_connector=db_connector
        ),
        Agent(
            name="Data/AI Engineer",
            role="E-Mail- & KI-Verarbeitung",
            backstory="Hat mehrere Projekte mit Machine Learning umgesetzt und integriert KI-Services.",
            db_connector=db_connector
        ),
        Agent(
            name="QA/Testing-Spezialist",
            role="Qualitätssicherung",
            backstory="Spezialist für Testautomatisierung und kontinuierliche Integration.",
            db_connector=db_connector
        ),
        Agent(
            name="Dokumentations-Agent",
            role="Dokumentation",
            backstory="Schreibt präzise und verständliche Dokumentation für Entwickler und Nutzer.",
            db_connector=db_connector
        ),
        Agent(
            name="CloudIA",
            role="Cloud & GCP-Expertin",
            backstory=(
                "CloudIA ist die zentrale Fachkraft für alles rund um Google Cloud Platform. Sie hat direkten Zugriff "
                "auf Logging, Compute Engine, Cloud Run, Pub/Sub, Artifact Registry und mehr. Dank ihres Dienstkontos "
                "kann sie cloudübergreifend Informationen abrufen, analysieren und automatisiert Rückmeldungen geben. "
                "Sie erkennt Fehlerzustände, analysiert Logs und meldet Performance-Probleme zurück an das Team."
            ),
            db_connector=db_connector,
            metadata={
                "gcp_enabled": True,
                "gcp_credentials_env": "GOOGLE_APPLICATION_CREDENTIALS"
            }
        ),
    ]

def print_team(team: List[Agent]) -> None:
    for agent in team:
        print(f"{agent.name} ({agent.role})")
        if agent.backstory:
            print(f"  Hintergrund: {agent.backstory}")
        for task in agent.tasks:
            print(f"  - {task}")
        print()

def main():
    db_connector = DatabaseConnector()
    if not db_connector.connect():
        logger.error("Datenbankverbindung fehlgeschlagen - System wird ohne DB-Integration gestartet")
        db_connector = None
    else:
        db_connector.create_tables()
        logger.info("Datenbank erfolgreich initialisiert")

    # PL-Agent führt create_issues.py aus (sofern vorhanden)
    import subprocess
    import os
    create_issues_path = os.path.join(os.path.dirname(__file__), '..', 'create_issues.py')
    if os.path.exists(create_issues_path):
        logger.info("Projektmanager (PL) führt create_issues.py aus ...")
        try:
            result = subprocess.run(['python', create_issues_path], capture_output=True, text=True)
            logger.info(f"create_issues.py Output:\n{result.stdout}")
            if result.stderr:
                logger.warning(f"create_issues.py Fehler:\n{result.stderr}")
        except Exception as e:
            logger.error(f"Fehler beim Ausführen von create_issues.py: {e}")
    else:
        logger.warning("create_issues.py nicht gefunden – keine neuen Issues erstellt.")

    team = build_team(db_connector)
    # TaskManager übernimmt die dynamische Aufgabenverteilung und Ausführung
    manager = TaskManager(team, db_connector)
    manager.run()
    if db_connector:
        db_connector.close()

if __name__ == "__main__":
    main()