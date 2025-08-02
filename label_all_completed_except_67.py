import os
from github import Github

github_token = os.environ.get("GITHUB_TOKEN")
if not github_token:
    print("Kein GitHub-Token gefunden!")
    exit(1)

g = Github(github_token)
repo = g.get_repo("HystDevTV/PEARv2")

# Alle offenen Issues ohne Label 'completed-by-agent', außer #67
for issue in repo.get_issues(state="open"):
    if getattr(issue, 'pull_request', False):
        continue
    if issue.number == 67:
        continue
    labels = [label.name for label in getattr(issue, 'labels', [])]
    if "completed-by-agent" not in labels:
        issue.add_to_labels("completed-by-agent")
        print(f"Label 'completed-by-agent' zu Issue #{issue.number} hinzugefügt.")
print("Fertig.")
