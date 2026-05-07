#!/bin/bash
# One-time setup: enable Claude Code telemetry + start local collector
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETTINGS="$HOME/.claude/settings.json"
SERVICE="$HOME/.config/systemd/user/claude-metrics-collector.service"

echo "=== Claude Code Usage Dashboard 설정 ==="

# ── 1. Claude Code 텔레메트리 설정 ────────────────────────────────
echo ""
echo "[1/3] ~/.claude/settings.json 에 텔레메트리 설정 추가..."

mkdir -p "$(dirname "$SETTINGS")"

if [ -f "$SETTINGS" ]; then
  python3 - "$SETTINGS" <<'EOF'
import json, sys
path = sys.argv[1]
with open(path) as f:
    s = json.load(f)
s.setdefault("env", {}).update({
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/json",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
    "OTEL_METRIC_EXPORT_INTERVAL": "60000",
})
with open(path, 'w') as f:
    json.dump(s, f, indent=2)
print("  업데이트 완료")
EOF
else
  cat > "$SETTINGS" <<JSON
{
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/json",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
    "OTEL_METRIC_EXPORT_INTERVAL": "60000"
  }
}
JSON
  echo "  생성 완료"
fi

# ── 2. systemd 서비스 등록 ─────────────────────────────────────────
echo ""
echo "[2/3] systemd user 서비스 등록..."

mkdir -p "$(dirname "$SERVICE")"
cat > "$SERVICE" <<EOF
[Unit]
Description=Claude Code Metrics Collector
After=network.target

[Service]
ExecStart=/usr/bin/python3 ${SCRIPT_DIR}/collector/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable claude-metrics-collector
systemctl --user restart claude-metrics-collector
echo "  서비스 시작됨 (claude-metrics-collector)"

# ── 3. 시간별 자동 sync cron ──────────────────────────────────────
echo ""
echo "[3/3] 매 시간 자동 sync cron 등록..."

CRON_CMD="0 * * * * cd ${SCRIPT_DIR} && python3 collector/sync.py >> /tmp/claude-metrics-sync.log 2>&1"
( crontab -l 2>/dev/null | grep -v "claude-usage-dashboard"; echo "$CRON_CMD" ) | crontab -
echo "  등록 완료"

# ── 완료 ──────────────────────────────────────────────────────────
echo ""
echo "=== 설정 완료 ==="
echo ""
echo "대시보드: https://chaehee-hong.github.io/claude-usage-dashboard/"
echo ""
echo "수동 sync:  python3 ${SCRIPT_DIR}/collector/sync.py"
echo "로그 확인:  journalctl --user -u claude-metrics-collector -f"
echo "서비스 상태: systemctl --user status claude-metrics-collector"
