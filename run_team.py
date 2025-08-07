#from crewai import Agent as CrewAgent, Crew, Task
from modules.team import build_team, Agent as PEARAgent  # ⬅️ Stelle sicher, dass du DEINE Klasse importierst!
import requests
import os
from modules.team import build_team

team = build_team()
for agent in team:
    print(f"{agent.name} ({agent.role})")
# GitHub-Zugangsdaten (am besten als Umgebungsvariable speichern)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = "HystDevTV/PEARv2.2"

def lade_github_issues():
    url = f"https://api.github.com/repos/{REPO}/issues"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

# Team laden und CrewAI-Agenten erzeugen (inkl. Backstory)
def build_team():
    # Definiere manuell dein Team – oder importiere vorhandene Daten
    agenten_roh = [
        Agent(name="Infra-Agent", role="infrastructure", skills=["CI/CD", "Docker"]),
        Agent(name="Feature-Agent", role="feature", skills=["Python", "FastAPI"]),
        Agent(name="Workflow-Agent", role="workflow", skills=["Doku", "Abläufe"]),
        Agent(name="Onboard-Agent", role="onboarding", skills=["Training", "Wissen"]),
    ]

    # Wandeln in CrewAI-kompatible Agenten
    crewai_team = [
        CrewAgent(
            name=ag.name,
            role=ag.role,
            goal=" und ".join(ag.skills),
            backstory=f"{ag.name} ist zuständig für {ag.role} Aufgaben mit den Skills {', '.join(ag.skills)}."
        )
        for ag in agenten_roh
    ]

    return crewai_team

# GitHub Issues laden und als Tasks zuweisen
issues = lade_github_issues()
tasks = []
for i, issue in enumerate(issues):
    if "pull_request" in issue:
        continue  # PRs überspringen
    tasks.append(
        Task(
            description=issue["title"] + "\n" + (issue.get("body") or ""),
            expected_output="Löse das Issue.",
        )
    )

# Crew erzeugen
crew = Crew(
    agents=crewai_agents,
    tasks=tasks
)

# Ausgabe der Aufgabenverteilung
for task in tasks:
    print(f"Task für Agent {task.agent.role}: {task.description}")

if __name__ == "__main__":
    crew.kickoff()