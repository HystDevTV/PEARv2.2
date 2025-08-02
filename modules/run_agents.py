import os
import requests
from pathlib import Path
import sys
import threading
import time

# ``team.py`` liegt eine Ebene höher im Repository.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from team import build_team

def create_github_issue(title, body):
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    REPO = "HystdevTV/PEARv2"  # z.B. "HystDevTV/PEARv2"
    url = f"https://api.github.com/repos/{REPO}/issues"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    data = {"title": title, "body": body}
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    print(f"Issue erstellt: {title}")

def agent_worker(agent, team=None):
    print(f"{agent.name} startet Aufgabenbearbeitung...")
    if agent.role == "Koordination" and team is not None:
        # Automatisierung: Für jede Aufgabe der anderen Agenten ein Issue anlegen
        for other in team:
            if other is agent:
                continue
            for task in other.tasks:
                issue_title = f"{other.role}: {task}"
                issue_body = f"Automatisch erstellt durch den Projektmanager für {other.name} ({other.role})"
                create_github_issue(issue_title, issue_body)
                time.sleep(0.5)  # Optional: kleine Pause zwischen den Requests
    else:
        for task in agent.tasks:
            print(f"{agent.name} erledigt: {task}")
            time.sleep(1)
    print(f"{agent.name} hat alle Aufgaben erledigt.\n")

def run_agents() -> None:
    team = build_team()
    threads = []
    for agent in team:
        # Dem Projektleiter das ganze Team übergeben, den anderen nicht nötig
        args = (agent, team) if agent.role == "Koordination" else (agent,)
        t = threading.Thread(target=agent_worker, args=args)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    print("Alle Agenten sind fertig!")

if __name__ == "__main__":
    run_agents()