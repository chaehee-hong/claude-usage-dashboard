# Claude Code Usage Dashboard

Claude Code 토큰 사용량을 자동으로 수집해 GitHub Pages 대시보드로 시각화합니다.

## 대시보드

**https://chaehee-hong.github.io/claude-usage-dashboard/**

- 일별 토큰 사용량 (입력 / 출력 / 캐시)
- 모델별 사용량 및 API 기준 비용
- 최근 API 요청 목록
- 12시간마다 자동 업데이트

## 구조

```
Claude Code 사용
    │
    ├── ~/.claude/projects/**/*.jsonl   ← 세션 트랜스크립트 (로컬 자동 저장)
    │
    └── collector/server.py             ← OTLP 수신 서버 (port 4318, 실시간)
            │
            └── ~/.local/share/claude-metrics/data.json

                    ↓ 12시간마다 cron

            collector/sync.py           ← 트랜스크립트 파싱 + 비용 계산
                    │
                    └── dashboard/data.json
                                │
                                └── git push → GitHub Actions → GitHub Pages
```

## 파일 설명

| 파일 | 역할 |
|---|---|
| `collector/server.py` | 로컬 OTLP/HTTP 수신 서버 (port 4318). Claude Code가 실시간으로 메트릭을 전송 |
| `collector/sync.py` | 로컬 트랜스크립트를 파싱해 토큰·비용을 집계하고 GitHub에 push |
| `dashboard/index.html` | GitHub Pages 정적 대시보드 (Chart.js) |
| `dashboard/data.json` | 집계된 메트릭 데이터. sync.py가 업데이트하고 Pages가 서빙 |
| `.github/workflows/deploy.yml` | `dashboard/` 변경 시 GitHub Pages 자동 배포 |
| `setup.sh` | 최초 1회 설정 (systemd 서비스 등록, cron 추가, Claude Code 텔레메트리 활성화) |

## 비용 계산 기준

Anthropic 공식 API 가격 기준 추정치입니다 (구독 요금과 무관).

| 모델 | 입력 | 출력 | 캐시 읽기 | 캐시 쓰기 |
|---|---|---|---|---|
| claude-sonnet-4-6 | $3.00 / MTok | $15.00 / MTok | $0.30 / MTok | $3.75 / MTok |
| claude-haiku-4-5 | $0.80 / MTok | $4.00 / MTok | $0.08 / MTok | $1.00 / MTok |
| claude-opus-4-7 | $15.00 / MTok | $75.00 / MTok | $1.50 / MTok | $18.75 / MTok |

## 초기 설정

```bash
git clone https://github.com/chaehee-hong/claude-usage-dashboard
cd claude-usage-dashboard
bash setup.sh
```

`setup.sh` 가 하는 일:
- `~/.claude/settings.json` 에 OTel 텔레메트리 설정 추가
- `collector/server.py` 를 systemd user 서비스로 등록
- 12시간마다 `sync.py` 를 실행하는 cron 등록

## 수동 업데이트

```bash
python3 collector/sync.py
```

트랜스크립트 파싱 → `data.json` 갱신 → git push → Pages 배포까지 한 번에 실행됩니다.
