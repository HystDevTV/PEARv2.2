import os
from typing import List, Dict, Any
from datetime import datetime
import logging
from github import Github, Issue
from google.cloud import storage

# Konfiguration
PROJECT_ID = "pear-dev-teamv1"
CONTAINER_REGISTRY = f"gcr.io/{PROJECT_ID}/dev-team-pear-agenten:latest"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "HystDevTV/PEARv2"

# Logging einrichten
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PEAR-Team")

class Agent:
    def __init__(self, name: str, role: str, skills: List[str]):
        self.name = name
        self.role = role
        self.skills = skills
        self.assigned_tasks = []
        self.status = "idle"
        logger.info(f"Agent {name} mit Rolle '{role}' initialisiert")
    
    def assign_task(self, task: Dict[str, Any]) -> bool:
        """Weist dem Agenten eine Aufgabe zu"""
        if self.status == "busy":
            logger.warning(f"Agent {self.name} ist beschäftigt. Aufgabe abgelehnt.")
            return False
        
        self.assigned_tasks.append(task)
        self.status = "busy"
        logger.info(f"Aufgabe '{task['title']}' an Agent {self.name} zugewiesen")
        return True
    
    def execute_tasks(self) -> List[Dict[str, Any]]:
        """Führt alle zugewiesenen Aufgaben aus"""
        results = []
        for task in self.assigned_tasks:
            logger.info(f"Agent {self.name} bearbeitet Aufgabe '{task['title']}'")
            # Hier würde die eigentliche Logik zur Aufgabenbearbeitung kommen
            # Je nach Rolle des Agenten
            result = self._process_task(task)
            results.append(result)
            
            # Feedback in GitHub Issue hinterlegen
            if task.get('issue_number'):
                self._update_github_issue(task, result)
        
        self.assigned_tasks = []
        self.status = "idle"
        return results
    
    def _process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Verarbeitet eine einzelne Aufgabe basierend auf der Rolle des Agenten"""
        # Diese Methode würde in einer erweiterten Implementierung
        # für jede Agent-Unterklasse überschrieben werden
        if self.role == "infrastructure":
            # Infrastruktur-Logik
            return self._process_infrastructure_task(task)
        elif self.role == "feature":
            # Feature-Logik
            return self._process_feature_task(task)
        elif self.role == "workflow":
            # Workflow-Logik
            return self._process_workflow_task(task)
        elif self.role == "onboarding":
            # Onboarding-Logik
            return self._process_onboarding_task(task)
        
        # Fallback
        return {"status": "completed", "message": f"Aufgabe bearbeitet von {self.name}"}
    
    def _update_github_issue(self, task: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Aktualisiert das GitHub Issue mit dem Ergebnis"""
        if not GITHUB_TOKEN:
            logger.warning("Kein GitHub-Token verfügbar. Issue-Update übersprungen.")
            return
            
        try:
            g = Github(GITHUB_TOKEN)
            repo = g.get_repo(GITHUB_REPO)
            issue = repo.get_issue(task['issue_number'])
            
            comment = f"## Aufgabe abgeschlossen von {self.name}\n\n"
            comment += f"**Status**: {result['status']}\n\n"
            comment += f"**Nachricht**: {result['message']}\n\n"
            comment += f"**Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            issue.create_comment(comment)
            
            if result['status'] == "completed":
                # Optional: Label hinzufügen oder Issue schließen
                issue.add_to_labels("completed-by-agent")
            
            logger.info(f"GitHub Issue #{task['issue_number']} aktualisiert")
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des GitHub Issues: {str(e)}")
    
    # Spezifische Task-Verarbeitungsmethoden je nach Agentenrolle
    def _process_infrastructure_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Verarbeitet Infrastruktur-Aufgaben (Kategorie A)"""
        logger.info(f"Infrastructure Agent verarbeitet: {task['title']}")
        # Implementiere hier die spezifische Logik für Infrastrukturaufgaben
        return {"status": "completed", "message": "Infrastruktur-Aufgabe abgeschlossen"}
    
    def _process_feature_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Verarbeitet Feature-Aufgaben (Kategorie B)"""
        logger.info(f"Feature Agent verarbeitet: {task['title']}")
        # Implementiere hier die spezifische Logik für Feature-Aufgaben
        return {"status": "completed", "message": "Feature-Aufgabe abgeschlossen"}
    
    def _process_workflow_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Verarbeitet Workflow-Aufgaben (Kategorie C)"""
        logger.info(f"Workflow Agent verarbeitet: {task['title']}")
        # Implementiere hier die spezifische Logik für Workflow-Aufgaben
        return {"status": "completed", "message": "Workflow-Aufgabe abgeschlossen"}
    
    def _process_onboarding_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Verarbeitet Onboarding-Aufgaben (Kategorie D)"""
        logger.info(f"Onboarding Agent verarbeitet: {task['title']}")
        # Implementiere hier die spezifische Logik für Onboarding-Aufgaben
        return {"status": "completed", "message": "Onboarding-Aufgabe abgeschlossen"}
    
    @classmethod
    def from_container(cls, container_url: str, role: str) -> 'Agent':
        """Erstellt einen Agenten aus einem Container-Image"""
        # In einer realen Implementierung würde hier der Agent aus dem Container geladen
        name = f"PEAR-{role.capitalize()}-Agent"
        skills = []
        
        # Skills je nach Rolle definieren
        if role == "infrastructure":
            skills = ["Docker", "Cloud Build", "GCP", "CI/CD"]
        elif role == "feature":
            skills = ["Python", "API", "Automatisierung"]
        elif role == "workflow":
            skills = ["Dokumentation", "Prozessoptimierung"]
        elif role == "onboarding":
            skills = ["Training", "Wissensmanagement"]
        
        return cls(name, role, skills)


class TaskManager:
    def __init__(self, github_repo: str = GITHUB_REPO):
        self.github_repo = github_repo
        self.agents = []
        logger.info(f"TaskManager für Repository {github_repo} initialisiert")
    
    def register_agent(self, agent: Agent) -> None:
        """Registriert einen Agenten beim TaskManager"""
        self.agents.append(agent)
        logger.info(f"Agent {agent.name} registriert")
    
    def fetch_tasks_from_github(self) -> List[Dict[str, Any]]:
        """Holt offene Aufgaben aus GitHub Issues"""
        if not GITHUB_TOKEN:
            logger.warning("Kein GitHub-Token verfügbar. Verwende Dummy-Aufgaben.")
            return self._get_dummy_tasks()
            
        try:
            g = Github(GITHUB_TOKEN)
            repo = g.get_repo(self.github_repo)
            open_issues = repo.get_issues(state="open")
            
            tasks = []
            for issue in open_issues:
                # Kategorie aus Labels oder Beschreibung extrahieren
                category = self._extract_category(issue)
                
                task = {
                    "title": issue.title,
                    "description": issue.body,
                    "category": category,
                    "issue_number": issue.number,
                    "labels": [label.name for label in issue.labels]
                }
                tasks.append(task)
            
            logger.info(f"{len(tasks)} Aufgaben aus GitHub Issues geholt")
            return tasks
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der GitHub Issues: {str(e)}")
            return self._get_dummy_tasks()
    
    def _extract_category(self, issue: Issue) -> str:
        """Extrahiert die Kategorie (A, B, C, D) aus einem GitHub Issue"""
        body = issue.body or ""
        
        if any(label.name.lower() in ["infrastructure", "kategorie-a"] for label in issue.labels):
            return "A"
        elif any(label.name.lower() in ["feature", "kategorie-b"] for label in issue.labels):
            return "B"
        elif any(label.name.lower() in ["workflow", "kategorie-c"] for label in issue.labels):
            return "C"
        elif any(label.name.lower() in ["onboarding", "kategorie-d"] for label in issue.labels):
            return "D"
        
        # Aus Beschreibung extrahieren
        if "A. CI/CD" in body or "Infrastruktur" in body:
            return "A"
        elif "B. PEAR Feature" in body or "Feature-Automatisierung" in body:
            return "B"
        elif "C. Dev- und Workflow" in body or "Workflow-Optimierung" in body:
            return "C"
        elif "D. Team Onboarding" in body or "Wissensmanagement" in body:
            return "D"
        
        # Fallback
        return "unknown"
    
    def _get_dummy_tasks(self) -> List[Dict[str, Any]]:
        """Erstellt Dummy-Aufgaben für Tests ohne GitHub-Anbindung"""
        return [
            {
                "title": "CI/CD Pipeline abschließen",
                "description": "Monitoring aktivieren (Cloud Run Healthchecks, Logging-Alerts, Benachrichtigungen)",
                "category": "A",
                "issue_number": None
            },
            {
                "title": "Automatische Registrierung einrichten",
                "description": "Implementieren: Jeder Agent/Service aus team.py wird automatisiert gebaut & deployed",
                "category": "B",
                "issue_number": None
            },
            {
                "title": "README und Canvas-Daten aktualisieren",
                "description": "Checkliste: Jeder im Team versteht den Flow",
                "category": "C",
                "issue_number": None
            },
            {
                "title": "Onboarding-Dokumente bereitstellen",
                "description": "Onboarding-Doku für neue Entwickler bereitstellen",
                "category": "D",
                "issue_number": None
            }
        ]
    
    def assign_tasks_by_category(self, agents: List[Agent] = None) -> None:
        """Weist Aufgaben nach Kategorie zu"""
        if agents:
            self.agents = agents
        
        if not self.agents:
            logger.warning("Keine Agenten registriert. Aufgabenzuweisung übersprungen.")
            return
        
        tasks = self.fetch_tasks_from_github()
        
        # Agenten nach Rolle gruppieren
        agent_by_role = {}
        for agent in self.agents:
            if agent.role not in agent_by_role:
                agent_by_role[agent.role] = []
            agent_by_role[agent.role].append(agent)
        
        # Aufgaben nach Kategorie und Priorität zuweisen
        for task in sorted(tasks, key=lambda x: self._get_priority(x)):
            category = task["category"]
            assigned = False
            
            # Kategorie zu Rolle mappen
            role = self._map_category_to_role(category)
            
            # Verfügbare Agenten für diese Rolle finden
            available_agents = agent_by_role.get(role, [])
            for agent in available_agents:
                if agent.status == "idle":
                    agent.assign_task(task)
                    assigned = True
                    break
            
            if not assigned:
                logger.warning(f"Keine verfügbaren Agenten für Aufgabe: {task['title']}")
    
    def _map_category_to_role(self, category: str) -> str:
        """Mappt eine Kategorie (A,B,C,D) zu einer Agentenrolle"""
        mapping = {
            "A": "infrastructure",
            "B": "feature",
            "C": "workflow",
            "D": "onboarding",
            "unknown": "feature"  # Fallback
        }
        return mapping.get(category, "feature")
    
    def _get_priority(self, task: Dict[str, Any]) -> int:
        """Bestimmt die Priorität einer Aufgabe (niedriger Wert = höhere Priorität)"""
        # Priorität basierend auf Kategorie
        category_priority = {"A": 0, "B": 1, "C": 2, "D": 3, "unknown": 4}
        
        # Titel-basierte Priorität
        title_priority = 0
        title = task["title"].lower()
        if "kritisch" in title or "dringend" in title:
            title_priority -= 2
        if "bug" in title or "fehler" in title:
            title_priority -= 1
        
        # Labels prüfen
        labels_priority = 0
        for label in task.get("labels", []):
            if "priority" in label.lower():
                try:
                    # z.B. "priority-1" -> -1
                    priority_value = int(label.split("-")[1])
                    labels_priority -= priority_value
                except:
                    pass
        
        base_priority = category_priority.get(task["category"], 4)
        return base_priority + title_priority + labels_priority
    
    def execute_all(self) -> None:
        """Führt alle zugewiesenen Aufgaben aus"""
        for agent in self.agents:
            if agent.assigned_tasks:
                logger.info(f"Agent {agent.name} führt {len(agent.assigned_tasks)} Aufgaben aus")
                agent.execute_tasks()


def main():
    """Hauptfunktion zum Starten des PEAR-Teams"""
    logger.info("PEAR Team wird initialisiert")
    
    # Agenten erstellen
    agents = [
        Agent.from_container(CONTAINER_REGISTRY, "infrastructure"),
        Agent.from_container(CONTAINER_REGISTRY, "feature"),
        Agent.from_container(CONTAINER_REGISTRY, "workflow"),
        Agent.from_container(CONTAINER_REGISTRY, "onboarding")
    ]
    
    # TaskManager initialisieren
    task_manager = TaskManager(GITHUB_REPO)
    
    # Aufgaben zuweisen und ausführen
    task_manager.assign_tasks_by_category(agents)
    task_manager.execute_all()
    
    logger.info("PEAR Team hat alle Aufgaben abgeschlossen")


if __name__ == "__main__":
    main()