#!/usr/bin/env python3
"""
Copy local metrics to dashboard/data.json and push to GitHub.
Run manually or via cron: 0 * * * * cd /path/to/repo && python3 collector/sync.py
"""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

DATA_FILE = Path.home() / ".local" / "share" / "claude-metrics" / "data.json"
REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DATA = REPO_ROOT / "dashboard" / "data.json"


def main():
    if not DATA_FILE.exists():
        print(f"No data at {DATA_FILE}")
        print("Is collector/server.py running?")
        sys.exit(1)

    data = json.loads(DATA_FILE.read_text())

    DASHBOARD_DATA.write_text(json.dumps(data, indent=2))
    print(f"Synced → {DASHBOARD_DATA}")
    print(f"  {len(data.get('daily', {}))} days, {len(data.get('recent_events', []))} events")

    result = subprocess.run(
        ["git", "diff", "--quiet", "dashboard/data.json"],
        cwd=REPO_ROOT,
    )
    if result.returncode == 0:
        print("No changes — nothing to push.")
        return

    subprocess.run(["git", "add", "dashboard/data.json"], cwd=REPO_ROOT, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"metrics: {date.today()}"],
        cwd=REPO_ROOT, check=True,
    )
    subprocess.run(["git", "push"], cwd=REPO_ROOT, check=True)
    print("Pushed to GitHub.")


if __name__ == "__main__":
    main()
