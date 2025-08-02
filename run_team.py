from crewai import Agent as CrewAgent, Crew, Task
import requests
import os
from modules.team import build_team

team = build_team()
for agent in team:
    print(f"{agent.name} ({agent.role})")
# GitHub-Zugangsdaten (am besten als Umgebungsvariable speichern)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = "HystDevTV/PEARv2"

def lade_github_issues():
    url = f"https://api.github.com/repos/{REPO}/issues"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

# Team laden und CrewAI-Agenten erzeugen (inkl. Backstory)
projekt_team = build_team()
crewai_agents = [
    CrewAgent(
        name=ag.name,
        role=ag.role,
        goal=" und ".join(ag.tasks),
        backstory=ag.backstory
    )
    for ag in projekt_team
]

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
            agent=crewai_agents[i % len(crewai_agents)],  # Aufgaben rotierend zuweisen
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