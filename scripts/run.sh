#!/usr/bin/env bash
# Launcher (macOS / Linux / Git Bash): same idea as run.ps1
# Usage from repo root:
#   ./scripts/run.sh serve              # port from NTP_PORT or 8000
#   NTP_PORT=8765 ./scripts/run.sh serve
#   ./scripts/run.sh stop               # free NTP_PORT (or 8000), needs lsof or fuser
#   ./scripts/run.sh restart
#   ./scripts/run.sh setup | train | train-quick | test | doctor | worker

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY=".venv/bin/python"
CMD="${1:-serve}"
PORT="${NTP_PORT:-8000}"

banner_serve() {
  local p="$1"
  echo ""
  echo "  News Trust Platform"
  echo "  -------------------"
  echo "  Dashboard:  http://127.0.0.1:${p}/#dashboard"
  echo "  Quick demo: http://127.0.0.1:${p}/?demo=1#dashboard"
  echo "  Queue API:  http://127.0.0.1:${p}/api/v1/jobs/submit"
  echo "  (OpenAPI not served; use /api/health and JSON endpoints.)"
  echo ""
}

stop_port() {
  local p="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -ti:"$p" 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
      echo "Stopping PID(s) on port $p: $pids"
      kill -9 $pids 2>/dev/null || true
    else
      echo "Nothing listening on port $p"
    fi
  elif command -v fuser >/dev/null 2>&1; then
    fuser -k "${p}/tcp" 2>/dev/null || echo "Nothing listening on port $p (or fuser failed)"
  else
    echo "Install lsof or fuser to use stop/restart, or use: make stop PORT=$p"
  fi
}

if [[ "$CMD" == "setup" ]]; then
  if [[ ! -x "$PY" ]]; then
    python3 -m venv .venv
  fi
  "$PY" -m pip install -U pip
  "$PY" -m pip install -e ".[dev]"
  echo "Setup done. Next: ./scripts/run.sh serve   (training optional: ./scripts/run.sh train-quick)"
  exit 0
fi

if [[ ! -x "$PY" ]]; then
  echo "No .venv found. Run first: ./scripts/run.sh setup"
  exit 1
fi

case "$CMD" in
  train)       "$PY" -m src.pipeline.run_train ;;
  train-quick) "$PY" -m src.pipeline.run_train --quick --skip-build ;;
  serve)
    export NTP_PORT="$PORT"
    banner_serve "$PORT"
    "$PY" manage.py runserver "127.0.0.1:$PORT"
    ;;
  worker)      "$PY" manage.py process_jobs --poll-interval 2 --worker-name unix-worker ;;
  stop) stop_port "$PORT" ;;
  restart)
    stop_port "$PORT"
    sleep 1
    export NTP_PORT="$PORT"
    banner_serve "$PORT"
    "$PY" manage.py runserver "127.0.0.1:$PORT"
    ;;
  test)        "$PY" -m pytest -q ;;
  doctor)      "$PY" -m src.pipeline.doctor ;;
  *)
    echo "Usage: $0 setup|serve|worker|stop|restart|train|train-quick|test|doctor"
    exit 1
    ;;
esac
