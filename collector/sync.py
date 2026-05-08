#!/usr/bin/env python3
"""
Parse Claude Code transcripts → dashboard/data.json → git push
Run manually or via cron: 0 * * * * cd /path/to/repo && python3 collector/sync.py
"""

import glob
import json
import os
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT      = Path(__file__).resolve().parent.parent
DASHBOARD_DATA = REPO_ROOT / "dashboard" / "data.json"


def parse_transcripts() -> tuple[dict, list]:
    daily       = defaultdict(lambda: {
        "tokens_input": 0, "tokens_output": 0,
        "tokens_cache_read": 0, "tokens_cache_creation": 0,
        "cost_usd": 0.0, "sessions": 0,
        "commits": 0, "lines_added": 0, "lines_removed": 0,
    })
    events      = []
    seen_ids    = set()
    files       = glob.glob(os.path.expanduser("~/.claude/projects/**/*.jsonl"), recursive=True)

    for fpath in files:
        session_counted = False
        try:
            with open(fpath, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue

                    if obj.get("type") != "assistant" or obj.get("isSidechain"):
                        continue

                    msg         = obj.get("message", {})
                    usage       = msg.get("usage", {})
                    msg_id      = msg.get("id", "")
                    stop_reason = msg.get("stop_reason", "")
                    timestamp   = obj.get("timestamp", "")

                    if not (usage and stop_reason in ("end_turn", "stop_sequence", "tool_use") and msg_id):
                        continue
                    if msg_id in seen_ids:
                        continue
                    seen_ids.add(msg_id)

                    try:
                        dt       = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        date_key = dt.strftime("%Y-%m-%d")
                    except Exception:
                        continue

                    inp = usage.get("input_tokens", 0)
                    out = usage.get("output_tokens", 0)
                    cr  = usage.get("cache_read_input_tokens", 0)
                    cc  = usage.get("cache_creation_input_tokens", 0)

                    daily[date_key]["tokens_input"]          += inp
                    daily[date_key]["tokens_output"]         += out
                    daily[date_key]["tokens_cache_read"]     += cr
                    daily[date_key]["tokens_cache_creation"] += cc

                    if not session_counted:
                        daily[date_key]["sessions"] += 1
                        session_counted = True

                    events.append({
                        "timestamp":             timestamp,
                        "model":                 msg.get("model", "unknown"),
                        "cost_usd":              0.0,
                        "input_tokens":          inp,
                        "output_tokens":         out,
                        "cache_read_tokens":     cr,
                        "cache_creation_tokens": cc,
                        "duration_ms":           0,
                        "query_source":          "main",
                    })
        except Exception:
            pass

    events.sort(key=lambda e: e.get("timestamp", ""))
    return dict(sorted(daily.items())), events[-300:]


def main():
    print("트랜스크립트 파싱 중...")
    daily, events = parse_transcripts()

    data = {"daily": daily, "by_model": {}, "recent_events": events}
    DASHBOARD_DATA.write_text(json.dumps(data, indent=2))

    total_out = sum(v["tokens_output"] for v in daily.values())
    print(f"  {len(daily)}일 · 출력 토큰 {total_out:,} · 이벤트 {len(events)}개")

    result = subprocess.run(
        ["git", "diff", "--quiet", "dashboard/data.json"],
        cwd=REPO_ROOT,
    )
    if result.returncode == 0:
        print("변경 없음 — push 스킵.")
        return

    subprocess.run(["git", "add", "dashboard/data.json"], cwd=REPO_ROOT, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"metrics: {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
        cwd=REPO_ROOT, check=True,
    )
    subprocess.run(["git", "push"], cwd=REPO_ROOT, check=True)
    print("GitHub 에 push 완료.")


if __name__ == "__main__":
    main()
