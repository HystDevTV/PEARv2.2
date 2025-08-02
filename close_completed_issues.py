import os
from github import Github
from dotenv import load_dotenv

load_dotenv()
github_token = os.environ.get("GITHUB_TOKEN")
repo_name = "HystDevTV/PEARv2"

if not github_token:
    print("Fehler: GITHUB_TOKEN nicht gesetzt.")
    exit(1)

g = Github(github_token)
repo = g.get_repo(repo_name)

closed_count = 0
for issue in repo.get_issues(state="open", labels=["completed-by-agent"]):
    issue.edit(state="closed")
    print(f"Issue #{issue.number} geschlossen: {issue.title}")
    closed_count += 1

if closed_count == 0:
    print("Keine offenen Issues mit Label 'completed-by-agent' gefunden.")
else:
    print(f"{closed_count} Issues wurden geschlossen.")
