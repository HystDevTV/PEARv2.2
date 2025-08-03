import os
import requests
import sys
import time
import threading
from pathlib import Path
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parent.parent))
load_dotenv()

from team import build_team, TaskManager, extract_tasks_from_issue_body

def create_github_issue(title, body):
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    REPO = "HystdevTV/PEARv2.2"
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
        for task_issue in agent.tasks:
            parsed_tasks = extract_tasks_from_issue_body(task_issue["body"])

            for task_data in parsed_tasks:
                category = task_data["category"]
                task_text = task_data["task"]

                assigned = False
                for member in team:
                    if member is agent:
                        continue
                    if category.lower() in member.role.lower():
                        create_github_issue(
                            title=f"{member.role}: {task_text}",
                            body=f"Vom PL zugewiesen für {member.name} ({member.role})\n\n{task_text}"
                        )
                        member.tasks.append(task_text)
                        assigned = True
                        break

                if not assigned:
                    print(f"⚠️ Keine passende Rolle für: '{category}' → '{task_text}'")
    else:
        for task in agent.tasks:
            agent.execute_task(task, category=agent.role, priority=1)
            time.sleep(0.5)

        print(f"{agent.name} hat alle Aufgaben erledigt.\n")
        agent.report()

def run_agents():
    team = build_team()
    manager = TaskManager(team)
    manager.fetch_github_issues()
    manager.assign_tasks()

    threads = []
    for agent in team:
        args = (agent, team) if agent.role == "Koordination" else (agent,)
        t = threading.Thread(target=agent_worker, args=args)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    print("Alle Agenten sind fertig!")
    manager.report(final=True)

if __name__ == "__main__":
    run_agents()
