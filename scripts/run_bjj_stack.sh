#!/usr/bin/env bash

set -Eeuo pipefail

AI_SERVICE_MODE="${AI_SERVICE_MODE:-parity}"
if [[ "$AI_SERVICE_MODE" == "parity" ]]; then
  exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run_parity_stack.sh"
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AI_SERVICE_DIR="${AI_SERVICE_DIR:-$ROOT_DIR/ai-service}"
BJJ_APP_DIR="${BJJ_APP_DIR:-/home/marcos/Escritorio/TFG/pa/bjj-app}"
FRONTEND_DIR="${FRONTEND_DIR:-$BJJ_APP_DIR/frontend}"
VIDEOS_DIR="${VIDEOS_DIR:-/tmp/storage/videos}"
AI_PORT="${AI_PORT:-8081}"
BACKEND_PORT="${BACKEND_PORT:-8080}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
SPRING_POC_BASE_URL="${SPRING_POC_BASE_URL:-http://localhost:8090}"
WEBHOOK_SECRET="${AI_WEBHOOK_SECRET:-dev-webhook-secret-2025}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
NPM_BIN="${NPM_BIN:-npm}"
VENV_DIR="${VENV_DIR:-$AI_SERVICE_DIR/.venv}"
AI_LOG_FILE="${AI_LOG_FILE:-/tmp/bjj-ai-service.log}"
AI_PID_FILE="${AI_PID_FILE:-/tmp/bjj-ai-service.pid}"
FRONTEND_LOG_FILE="${FRONTEND_LOG_FILE:-/tmp/bjj-frontend.log}"
FRONTEND_PID_FILE="${FRONTEND_PID_FILE:-/tmp/bjj-frontend.pid}"
DEFAULT_YOLO_MODEL_PATH="$ROOT_DIR/ai-service/yolov8n-pose.pt"
if [[ ! -f "$DEFAULT_YOLO_MODEL_PATH" ]]; then
  DEFAULT_YOLO_MODEL_PATH="$ROOT_DIR/yolov8n-pose.pt"
fi
YOLO_MODEL_PATH="${YOLO_MODEL_PATH:-$DEFAULT_YOLO_MODEL_PATH}"

DEFAULT_RF_MODEL_PATH="$ROOT_DIR/python/models/bjj_pose_classifier.pkl"
RF_MODEL_PATH="${RF_MODEL_PATH:-$DEFAULT_RF_MODEL_PATH}"

DEFAULT_RF_LABEL_MAPPING_PATH="$ROOT_DIR/python/models/label_mapping.json"
RF_LABEL_MAPPING_PATH="${RF_LABEL_MAPPING_PATH:-$DEFAULT_RF_LABEL_MAPPING_PATH}"

port_in_use() {
  local port="$1"
  "$PYTHON_BIN" - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.2)
    result = sock.connect_ex(("127.0.0.1", port))
    sys.exit(0 if result == 0 else 1)
PY
}

if [[ ! -d "$BJJ_APP_DIR" ]]; then
  echo "BJJ_APP_DIR does not exist: $BJJ_APP_DIR" >&2
  exit 1
fi

if [[ ! -f "$BJJ_APP_DIR/docker-compose.yml" ]]; then
  echo "docker-compose.yml not found in BJJ_APP_DIR: $BJJ_APP_DIR" >&2
  exit 1
fi

if [[ ! -d "$AI_SERVICE_DIR" ]]; then
  echo "AI_SERVICE_DIR does not exist: $AI_SERVICE_DIR" >&2
  exit 1
fi

mkdir -p "$VIDEOS_DIR"
mkdir -p "$(dirname "$AI_LOG_FILE")"
mkdir -p "$(dirname "$AI_PID_FILE")"
mkdir -p "$(dirname "$FRONTEND_LOG_FILE")"
mkdir -p "$(dirname "$FRONTEND_PID_FILE")"
: >"$AI_LOG_FILE"
: >"$FRONTEND_LOG_FILE"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "[setup] Creating ai-service virtualenv at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

echo "[setup] Installing ai-service dependencies"
"$VENV_DIR/bin/pip" install -r "$AI_SERVICE_DIR/requirements.txt" >/dev/null

if [[ ! -d "$FRONTEND_DIR" || ! -f "$FRONTEND_DIR/package.json" ]]; then
  echo "FRONTEND_DIR is invalid: $FRONTEND_DIR" >&2
  exit 1
fi

echo "[setup] Installing frontend dependencies if needed"
if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  (
    cd "$FRONTEND_DIR"
    "$NPM_BIN" install
  )
fi

echo "[stack] Starting postgres and backend via docker compose (with backend rebuild)"
(
  cd "$BJJ_APP_DIR"
  docker compose up -d --build postgres backend
)

echo "[stack] Waiting for backend on http://localhost:$BACKEND_PORT/api/v1/health"
for _ in {1..60}; do
  if curl -sf "http://localhost:$BACKEND_PORT/api/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if port_in_use "$AI_PORT"; then
  echo "[error] Port $AI_PORT is already in use. Stop the existing process before starting the refactored ai-service." >&2
  exit 1
fi

if port_in_use "$FRONTEND_PORT"; then
  echo "[error] Port $FRONTEND_PORT is already in use. Stop the existing frontend process before starting a new one." >&2
  exit 1
fi

echo "[stack] Starting local ai-service on http://localhost:$AI_PORT"
(
  cd "$AI_SERVICE_DIR"
  export AI_WEBHOOK_SECRET="$WEBHOOK_SECRET"
  export LOCAL_STORAGE_DIR="$VIDEOS_DIR"
  export PORT="$AI_PORT"
  export YOLO_MODEL_PATH="$YOLO_MODEL_PATH"
  export RF_MODEL_PATH="$RF_MODEL_PATH"
  export RF_LABEL_MAPPING_PATH="$RF_LABEL_MAPPING_PATH"
  export MODEL_PATH="$YOLO_MODEL_PATH"
  export LOCAL_MODEL_PATH="$RF_MODEL_PATH"
  export LABEL_MAPPING_PATH="$RF_LABEL_MAPPING_PATH"
  export GEMINI_ENABLED="${GEMINI_ENABLED:-false}"
  export SPRING_POC_ENABLED="${SPRING_POC_ENABLED:-true}"
  export SPRING_POC_BASE_URL="$SPRING_POC_BASE_URL"
  export GEMINI_API_KEY="${GEMINI_API_KEY:-}"
  export GEMINI_MODEL="${GEMINI_MODEL:-gemini-flash-latest}"
  export GEMINI_TIMEOUT_SECONDS="${GEMINI_TIMEOUT_SECONDS:-45.0}"
  export GEMINI_MAX_FRAMES="${GEMINI_MAX_FRAMES:-8}"
  export GEMINI_SAMPLE_INTERVAL_SECONDS="${GEMINI_SAMPLE_INTERVAL_SECONDS:-2.0}"
  export DEBUG_FRAME_DECISIONS="${DEBUG_FRAME_DECISIONS:-false}"
  exec "$VENV_DIR/bin/python" -m uvicorn main:app --host 0.0.0.0 --port "$AI_PORT"
) >"$AI_LOG_FILE" 2>&1 &
AI_PID=$!
echo "$AI_PID" >"$AI_PID_FILE"

echo "[stack] Starting frontend locally on http://localhost:$FRONTEND_PORT"
(
  cd "$FRONTEND_DIR"
  export NEXT_PUBLIC_API_URL="http://localhost:$BACKEND_PORT"
  export PORT="$FRONTEND_PORT"
  export WATCHPACK_POLLING="${WATCHPACK_POLLING:-true}"
  export CHOKIDAR_USEPOLLING="${CHOKIDAR_USEPOLLING:-true}"
  export CHOKIDAR_INTERVAL="${CHOKIDAR_INTERVAL:-1000}"
  export WATCHPACK_POLLING_INTERVAL="${WATCHPACK_POLLING_INTERVAL:-1000}"
  exec "$NPM_BIN" run dev -- --webpack
) >"$FRONTEND_LOG_FILE" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" >"$FRONTEND_PID_FILE"

cleanup() {
  echo
  echo "[cleanup] Stopping local ai-service (pid=$AI_PID)"
  if kill -0 "$AI_PID" >/dev/null 2>&1; then
    kill "$AI_PID" >/dev/null 2>&1 || true
    wait "$AI_PID" 2>/dev/null || true
  fi
  rm -f "$AI_PID_FILE"
  echo "[cleanup] Stopping local frontend (pid=$FRONTEND_PID)"
  if kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
    wait "$FRONTEND_PID" 2>/dev/null || true
  fi
  rm -f "$FRONTEND_PID_FILE"
}

trap cleanup EXIT INT TERM

echo "[stack] Waiting for ai-service on http://localhost:$AI_PORT/health"
for _ in {1..60}; do
  if curl -sf "http://localhost:$AI_PORT/health" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$AI_PID" >/dev/null 2>&1; then
    echo "ai-service exited unexpectedly. Log output:" >&2
    cat "$AI_LOG_FILE" >&2
    exit 1
  fi
  sleep 2
done

echo "[stack] Waiting for frontend on http://localhost:$FRONTEND_PORT"
for _ in {1..60}; do
  if curl -sf "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    echo "frontend exited unexpectedly. Log output:" >&2
    cat "$FRONTEND_LOG_FILE" >&2
    exit 1
  fi
  sleep 2
done

echo "[ready] frontend=http://localhost:$FRONTEND_PORT backend=http://localhost:$BACKEND_PORT ai-service=http://localhost:$AI_PORT"
echo "[logs] Streaming postgres/backend docker logs plus prefixed frontend/ai-service logs. Ctrl-C stops the local processes and exits this script."

(
  cd "$BJJ_APP_DIR"
  docker compose logs -f postgres backend &
  DOCKER_LOGS_PID=$!
  stdbuf -oL tail -F "$AI_LOG_FILE" | sed -u 's/^/[ai-service] /' &
  AI_TAIL_PID=$!
  stdbuf -oL tail -F "$FRONTEND_LOG_FILE" | sed -u 's/^/[frontend] /' &
  FRONTEND_TAIL_PID=$!
  wait -n "$DOCKER_LOGS_PID" "$AI_TAIL_PID" "$FRONTEND_TAIL_PID"
) || true
