"""Once-daily independent verification of the existing five-minute live workflows."""
import os
from datetime import datetime, timezone
import requests

WORKFLOWS = ("job-radar.yml", "linkedin-radar.yml")


def verify_runs(runs, now):
    completed = [r for r in runs if r.get("status") == "completed" and r.get("head_branch") == "main"]
    if not completed:
        return False, "No completed main-branch runs"
    last = completed[0]
    created = datetime.fromisoformat(last["created_at"].replace("Z", "+00:00"))
    age_minutes = (now - created).total_seconds() / 60
    if age_minutes < -10 or age_minutes > 45:
        return False, f"Most recent completed run is stale ({age_minutes:.0f} min)"
    if len(completed) >= 2 and all(r.get("conclusion") != "success" for r in completed[:2]):
        return False, "At least two successive completed runs failed"
    return True, "Recent live workflow activity detected"


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ.get("GITHUB_TOKEN", "")
    now = datetime.now(timezone.utc)
    errors = []
    for workflow in WORKFLOWS:
        response = requests.get(
            f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs",
            params={"per_page": 8, "branch": "main"},
            headers={"Accept": "application/vnd.github+json", **({"Authorization": "Bearer " + token} if token else {})},
            timeout=20,
        )
        response.raise_for_status()
        good, explanation = verify_runs(response.json().get("workflow_runs", []), now)
        print(workflow, explanation)
        if not good:
            errors.append(workflow + ": " + explanation)
    if errors:
        raise SystemExit("Source health failures: " + "; ".join(errors))


if __name__ == "__main__":
    main()
