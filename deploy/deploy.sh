#!/usr/bin/env bash
set -euo pipefail

# 원격 PC 배포 스크립트 템플릿.
# 단일 서비스 기준. 멀티 서비스는 install/restart/smoke 블록을 서비스 수만큼 반복한다.
# {{...}} 플레이스홀더를 치환해 deploy/deploy.sh 로 둔다.

REPO_DIR="${REPO_DIR:-/root/.openclaw/workspace/repos/mth-english}"
BRANCH="${BRANCH:-main}"

# ── self-reexec ──
# bash는 시작 시점의 스크립트를 메모리에 들고 실행한다.
# 자기 자신을 git update한 효과를 보려면 새 버전으로 exec 재실행해야 한다.
# 1단계는 git update만 하고 끝낸다.
if [ -z "${DEPLOY_SCRIPT_REEXEC:-}" ]; then
  cd "$REPO_DIR"
  echo "[deploy] fetching latest from origin/$BRANCH (pre-exec)"
  git fetch origin "$BRANCH"
  git checkout "$BRANCH"
  git reset --hard "origin/$BRANCH"
  export DEPLOY_SCRIPT_REEXEC=1
  exec bash "$REPO_DIR/deploy/deploy.sh"
fi

# ── 이 지점부터는 새 코드의 deploy 본문 ──

APP_DIR="${APP_DIR:-/root/.openclaw/workspace/repos/mth-english/api}"
VENV_DIR="${VENV_DIR:-/root/.openclaw/workspace/repos/mth-english/.venv}"
SERVICE="mth-english"
PORT="8775"
HEALTH_PATH="/health"

cd "$REPO_DIR"

# ── 의존성 ──
if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi
if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "[deploy] missing venv at $VENV_DIR"
  exit 1
fi
"$VENV_DIR/bin/pip" install -q -r "$REPO_DIR/api/requirements.txt"   # 또는 명시적 패키지 목록

# ── systemd unit 설치 (repo = SSOT) ──
if command -v systemctl >/dev/null 2>&1 && [ -d /etc/systemd/system ]; then
  install -m 0644 "$REPO_DIR/deploy/$SERVICE.service" "/etc/systemd/system/$SERVICE.service"
  install -m 0644 "$REPO_DIR/deploy/cloudflared-$SERVICE.service" "/etc/systemd/system/cloudflared-$SERVICE.service"

  systemctl daemon-reload || true
  systemctl enable "$SERVICE.service"
  systemctl enable "cloudflared-$SERVICE.service" || true
  systemctl restart "$SERVICE.service"
  systemctl restart "cloudflared-$SERVICE.service" || true

  # ── smoke check: 프로세스가 떴는지가 아니라 요청에 답하는지 확인 ──
  "$VENV_DIR/bin/python" - "$PORT" "$HEALTH_PATH" <<'PY'
import sys, time, urllib.request
port, path = sys.argv[1], sys.argv[2]
url = f"http://127.0.0.1:{port}{path}"
last = None
for _ in range(20):
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            if r.status < 400:
                print(f"[deploy] smoke OK: {url}")
                break
            last = f"HTTP {r.status}"
    except Exception as exc:
        last = str(exc)
    time.sleep(0.5)
else:
    raise SystemExit(f"smoke check failed: {url}: {last}")
PY
  echo "[deploy] restarted systemd services"
else
  echo "[deploy] systemctl unavailable, manual restart required"
fi

echo "[deploy] done"
