#!/usr/bin/env python3
"""
Local OTLP/HTTP receiver for Claude Code telemetry.
Listens on port 4318 and saves metrics to ~/.local/share/claude-metrics/data.json
"""

import json
import sys
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 4318
DATA_FILE = Path.home() / ".local" / "share" / "claude-metrics" / "data.json"


def _get_attr(attrs: list, key: str):
    for a in attrs:
        if a.get("key") == key:
            v = a.get("value", {})
            for kind in ("stringValue", "intValue", "doubleValue", "boolValue"):
                if kind in v:
                    return v[kind]
    return None


def _dp_value(dp: dict) -> float:
    """Extract numeric value from an OTLP data point (handles asInt / asDouble)."""
    if "asInt" in dp:
        return float(dp["asInt"])
    if "asDouble" in dp:
        return float(dp["asDouble"])
    return 0.0


def load() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except Exception:
            pass
    return {"daily": {}, "by_model": {}, "recent_events": []}


def save(data: dict):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2))


def today() -> str:
    return date.today().isoformat()


def process_metrics(body: dict):
    data = load()
    day_key = today()
    day = data["daily"].setdefault(day_key, {
        "tokens_input": 0, "tokens_output": 0,
        "tokens_cache_read": 0, "tokens_cache_creation": 0,
        "cost_usd": 0.0, "sessions": 0,
        "commits": 0, "lines_added": 0, "lines_removed": 0,
    })

    for rm in body.get("resourceMetrics", []):
        for sm in rm.get("scopeMetrics", []):
            for metric in sm.get("metrics", []):
                name = metric.get("name", "")
                sum_data = metric.get("sum", {})

                for dp in sum_data.get("dataPoints", []):
                    attrs = dp.get("attributes", [])
                    value = _dp_value(dp)
                    model = _get_attr(attrs, "model") or "unknown"

                    if name == "claude_code.token.usage":
                        token_type = _get_attr(attrs, "type")
                        field = {
                            "input": "tokens_input",
                            "output": "tokens_output",
                            "cacheRead": "tokens_cache_read",
                            "cacheCreation": "tokens_cache_creation",
                        }.get(token_type)
                        if field:
                            day[field] = day.get(field, 0) + int(value)

                        bm = data["by_model"].setdefault(model, {
                            "tokens_input": 0, "tokens_output": 0,
                            "tokens_cache_read": 0, "tokens_cache_creation": 0,
                        })
                        if field:
                            bm[field] = bm.get(field, 0) + int(value)

                    elif name == "claude_code.cost.usage":
                        day["cost_usd"] = round(day.get("cost_usd", 0.0) + value, 6)

                    elif name == "claude_code.session.count":
                        day["sessions"] = day.get("sessions", 0) + int(value)

                    elif name == "claude_code.commit.count":
                        day["commits"] = day.get("commits", 0) + int(value)

                    elif name == "claude_code.lines_of_code.count":
                        line_type = _get_attr(attrs, "type")
                        if line_type == "added":
                            day["lines_added"] = day.get("lines_added", 0) + int(value)
                        elif line_type == "removed":
                            day["lines_removed"] = day.get("lines_removed", 0) + int(value)

    save(data)


def process_logs(body: dict):
    data = load()

    for rl in body.get("resourceLogs", []):
        for sl in rl.get("scopeLogs", []):
            for record in sl.get("logRecords", []):
                attrs = record.get("attributes", [])
                event_name = _get_attr(attrs, "event.name")

                if event_name == "claude_code.api_request":
                    data.setdefault("recent_events", []).append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "model": _get_attr(attrs, "model") or "unknown",
                        "cost_usd": float(_get_attr(attrs, "cost_usd") or 0),
                        "input_tokens": int(_get_attr(attrs, "input_tokens") or 0),
                        "output_tokens": int(_get_attr(attrs, "output_tokens") or 0),
                        "cache_read_tokens": int(_get_attr(attrs, "cache_read_tokens") or 0),
                        "cache_creation_tokens": int(_get_attr(attrs, "cache_creation_tokens") or 0),
                        "duration_ms": int(_get_attr(attrs, "duration_ms") or 0),
                        "query_source": _get_attr(attrs, "query_source") or "main",
                    })
                    data["recent_events"] = data["recent_events"][-300:]

    save(data)


class OTLPHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
            if self.path == "/v1/metrics":
                process_metrics(body)
            elif self.path == "/v1/logs":
                process_logs(body)
        except Exception as e:
            print(f"[ERROR] {self.path}: {e}", file=sys.stderr)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *_):
        pass  # suppress per-request logs


if __name__ == "__main__":
    print(f"Claude Code OTel receiver  →  http://localhost:{PORT}")
    print(f"Saving to: {DATA_FILE}")
    HTTPServer(("localhost", PORT), OTLPHandler).serve_forever()
