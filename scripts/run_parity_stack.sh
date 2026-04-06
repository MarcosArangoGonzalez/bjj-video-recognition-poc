#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AI_SERVICE_DIR="${AI_SERVICE_DIR:-$ROOT_DIR/ai-service}"
PYTHON_POC_DIR="${PYTHON_POC_DIR:-$ROOT_DIR/python}"
BJJ_APP_DIR="${BJJ_APP_DIR:-/home/marcos/Escritorio/TFG/pa/bjj-app}"
FRONTEND_DIR="${FRONTEND_DIR:-$BJJ_APP_DIR/frontend}"
VIDEOS_DIR="${VIDEOS_DIR:-/tmp/storage/videos}"

BACKEND_PORT="${BACKEND_PORT:-8080}"
AI_PORT="${AI_PORT:-8081}"
POC_SPRING_PORT="${POC_SPRING_PORT:-8090}"
POC_YOLO_PORT="${POC_YOLO_PORT:-8091}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

WEBHOOK_SECRET="${AI_WEBHOOK_SECRET:-dev-webhook-secret-2025}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
NPM_BIN="${NPM_BIN:-npm}"
MAVEN_BIN="${MAVEN_BIN:-mvn}"

AI_VENV_DIR="${AI_VENV_DIR:-$AI_SERVICE_DIR/.venv}"
POC_VENV_DIR="${POC_VENV_DIR:-$PYTHON_POC_DIR/.venv}"

AI_LOG_FILE="${AI_LOG_FILE:-/tmp/bjj-ai-service.log}"
FRONTEND_LOG_FILE="${FRONTEND_LOG_FILE:-/tmp/bjj-frontend.log}"
POC_YOLO_LOG_FILE="${POC_YOLO_LOG_FILE:-/tmp/bjj-poc-yolo.log}"
POC_SPRING_LOG_FILE="${POC_SPRING_LOG_FILE:-/tmp/bjj-poc-spring.log}"

AI_PID_FILE="${AI_PID_FILE:-/tmp/bjj-ai-service.pid}"
FRONTEND_PID_FILE="${FRONTEND_PID_FILE:-/tmp/bjj-frontend.pid}"
POC_YOLO_PID_FILE="${POC_YOLO_PID_FILE:-/tmp/bjj-poc-yolo.pid}"
POC_SPRING_PID_FILE="${POC_SPRING_PID_FILE:-/tmp/bjj-poc-spring.pid}"

DEFAULT_YOLO_MODEL_PATH="$ROOT_DIR/ai-service/yolov8n-pose.pt"
if [[ ! -f "$DEFAULT_YOLO_MODEL_PATH" ]]; then
  DEFAULT_YOLO_MODEL_PATH="$ROOT_DIR/yolov8n-pose.pt"
fi
YOLO_MODEL_PATH="${YOLO_MODEL_PATH:-$DEFAULT_YOLO_MODEL_PATH}"
RF_MODEL_PATH="${RF_MODEL_PATH:-$ROOT_DIR/python/models/bjj_pose_classifier.pkl}"
RF_LABEL_MAPPING_PATH="${RF_LABEL_MAPPING_PATH:-$ROOT_DIR/python/models/label_mapping.json}"

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

wait_for_http() {
  local url="$1"
  local label="$2"
  local max_tries="${3:-90}"
  for _ in $(seq 1 "$max_tries"); do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "[error] $label did not become healthy at $url" >&2
  return 1
}

mkdir -p "$VIDEOS_DIR"
mkdir -p "$(dirname "$AI_LOG_FILE")"
mkdir -p "$(dirname "$FRONTEND_LOG_FILE")"
mkdir -p "$(dirname "$POC_YOLO_LOG_FILE")"
mkdir -p "$(dirname "$POC_SPRING_LOG_FILE")"
: >"$AI_LOG_FILE"
: >"$FRONTEND_LOG_FILE"
: >"$POC_YOLO_LOG_FILE"
: >"$POC_SPRING_LOG_FILE"

if [[ ! -d "$AI_VENV_DIR" ]]; then
  echo "[setup] Creating ai-service virtualenv at $AI_VENV_DIR"
  "$PYTHON_BIN" -m venv "$AI_VENV_DIR"
fi
if [[ ! -d "$POC_VENV_DIR" ]]; then
  echo "[setup] Creating PoC python virtualenv at $POC_VENV_DIR"
  "$PYTHON_BIN" -m venv "$POC_VENV_DIR"
fi

echo "[setup] Installing ai-service dependencies"
"$AI_VENV_DIR/bin/pip" install -r "$AI_SERVICE_DIR/requirements.txt" >/dev/null

echo "[setup] Installing PoC python dependencies"
"$POC_VENV_DIR/bin/pip" install -r "$PYTHON_POC_DIR/requirements.txt" >/dev/null

echo "[setup] Installing frontend dependencies if needed"
if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  (
    cd "$FRONTEND_DIR"
    "$NPM_BIN" install
  )
fi

if port_in_use "$BACKEND_PORT"; then
  echo "[error] Port $BACKEND_PORT is already in use. Stop the current backend first." >&2
  exit 1
fi
if port_in_use "$AI_PORT"; then
  echo "[error] Port $AI_PORT is already in use." >&2
  exit 1
fi
if port_in_use "$POC_SPRING_PORT"; then
  echo "[error] Port $POC_SPRING_PORT is already in use." >&2
  exit 1
fi
if port_in_use "$POC_YOLO_PORT"; then
  echo "[error] Port $POC_YOLO_PORT is already in use." >&2
  exit 1
fi
if port_in_use "$FRONTEND_PORT"; then
  echo "[error] Port $FRONTEND_PORT is already in use." >&2
  exit 1
fi

echo "[stack] Starting bjj-app backend on http://localhost:$BACKEND_PORT"
(
  cd "$BJJ_APP_DIR"
  docker compose up -d --build postgres backend
)
wait_for_http "http://localhost:$BACKEND_PORT/api/v1/health" "bjj-app backend" 90

echo "[stack] Starting Flask YOLO PoC on http://localhost:$POC_YOLO_PORT"
(
  cd "$PYTHON_POC_DIR"
  export PORT="$POC_YOLO_PORT"
  export MODEL_PATH="$YOLO_MODEL_PATH"
  export LOCAL_MODEL_PATH="$RF_MODEL_PATH"
  export LABEL_MAPPING_PATH="$RF_LABEL_MAPPING_PATH"
  export USE_GPU="${USE_GPU:-true}"
  export ROBOFLOW_API_KEY="${ROBOFLOW_API_KEY:-}"
  exec "$POC_VENV_DIR/bin/python" yolov8_service.py
) >"$POC_YOLO_LOG_FILE" 2>&1 &
POC_YOLO_PID=$!
echo "$POC_YOLO_PID" >"$POC_YOLO_PID_FILE"
wait_for_http "http://localhost:$POC_YOLO_PORT/health" "PoC YOLO Flask" 120

echo "[stack] Starting Spring PoC on http://localhost:$POC_SPRING_PORT"
(
  cd "$ROOT_DIR"
  exec "$MAVEN_BIN" spring-boot:run "-Dspring-boot.run.jvmArguments=-Dserver.port=$POC_SPRING_PORT -Dyolov8.service.url=http://localhost:$POC_YOLO_PORT"
) >"$POC_SPRING_LOG_FILE" 2>&1 &
POC_SPRING_PID=$!
echo "$POC_SPRING_PID" >"$POC_SPRING_PID_FILE"
wait_for_http "http://localhost:$POC_SPRING_PORT/api/videos" "Spring PoC" 120

echo "[stack] Starting ai-service wrapper on http://localhost:$AI_PORT"
(
  cd "$AI_SERVICE_DIR"
  export AI_WEBHOOK_SECRET="$WEBHOOK_SECRET"
  export LOCAL_STORAGE_DIR="$VIDEOS_DIR"
  export PORT="$AI_PORT"
  export SPRING_POC_ENABLED="true"
  export SPRING_POC_BASE_URL="http://localhost:$POC_SPRING_PORT"
  export SPRING_POC_TIMEOUT_SECONDS="${SPRING_POC_TIMEOUT_SECONDS:-300}"
  export SPRING_POC_MAX_WAIT_SECONDS="${SPRING_POC_MAX_WAIT_SECONDS:-300}"
  export YOLO_MODEL_PATH="$YOLO_MODEL_PATH"
  export RF_MODEL_PATH="$RF_MODEL_PATH"
  export RF_LABEL_MAPPING_PATH="$RF_LABEL_MAPPING_PATH"
  export MODEL_PATH="$YOLO_MODEL_PATH"
  export LOCAL_MODEL_PATH="$RF_MODEL_PATH"
  export LABEL_MAPPING_PATH="$RF_LABEL_MAPPING_PATH"
  export GEMINI_ENABLED="false"
  exec "$AI_VENV_DIR/bin/python" -m uvicorn main:app --host 0.0.0.0 --port "$AI_PORT"
) >"$AI_LOG_FILE" 2>&1 &
AI_PID=$!
echo "$AI_PID" >"$AI_PID_FILE"
wait_for_http "http://localhost:$AI_PORT/health" "ai-service" 60

echo "[stack] Starting frontend on http://localhost:$FRONTEND_PORT"
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
wait_for_http "http://localhost:$FRONTEND_PORT" "frontend" 60

cleanup() {
  echo
  echo "[cleanup] Stopping local processes"
  for pid in "$AI_PID" "$FRONTEND_PID" "$POC_SPRING_PID" "$POC_YOLO_PID"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" 2>/dev/null || true
    fi
  done
  rm -f "$AI_PID_FILE" "$FRONTEND_PID_FILE" "$POC_YOLO_PID_FILE" "$POC_SPRING_PID_FILE"
}

trap cleanup EXIT INT TERM

echo "[ready] backend=http://localhost:$BACKEND_PORT frontend=http://localhost:$FRONTEND_PORT ai-service=http://localhost:$AI_PORT spring-poc=http://localhost:$POC_SPRING_PORT yolo-poc=http://localhost:$POC_YOLO_PORT"
echo "[logs] Ctrl-C stops local processes and exits."

(
  cd "$BJJ_APP_DIR"
  docker compose logs -f postgres backend &
  DOCKER_LOGS_PID=$!
  stdbuf -oL tail -F "$POC_YOLO_LOG_FILE" | sed -u 's/^/[poc-yolo] /' &
  POC_YOLO_TAIL_PID=$!
  stdbuf -oL tail -F "$POC_SPRING_LOG_FILE" | sed -u 's/^/[poc-spring] /' &
  POC_SPRING_TAIL_PID=$!
  stdbuf -oL tail -F "$AI_LOG_FILE" | sed -u 's/^/[ai-service] /' &
  AI_TAIL_PID=$!
  stdbuf -oL tail -F "$FRONTEND_LOG_FILE" | sed -u 's/^/[frontend] /' &
  FRONTEND_TAIL_PID=$!
  wait -n "$DOCKER_LOGS_PID" "$POC_YOLO_TAIL_PID" "$POC_SPRING_TAIL_PID" "$AI_TAIL_PID" "$FRONTEND_TAIL_PID"
) || true
