#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BJJ_APP_DIR="${BJJ_APP_DIR:-/home/marcos/Escritorio/TFG/pa/bjj-app}"
AI_PID_FILE="${AI_PID_FILE:-/tmp/bjj-ai-service.pid}"
FRONTEND_PID_FILE="${FRONTEND_PID_FILE:-/tmp/bjj-frontend.pid}"
POC_YOLO_PID_FILE="${POC_YOLO_PID_FILE:-/tmp/bjj-poc-yolo.pid}"
POC_SPRING_PID_FILE="${POC_SPRING_PID_FILE:-/tmp/bjj-poc-spring.pid}"
AI_PORT="${AI_PORT:-8081}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
POC_YOLO_PORT="${POC_YOLO_PORT:-8091}"
POC_SPRING_PORT="${POC_SPRING_PORT:-8090}"
STOP_DOCKER="${STOP_DOCKER:-true}"
REMOVE_DOCKER="${REMOVE_DOCKER:-false}"
FORCE_PORT_CLEANUP="${FORCE_PORT_CLEANUP:-false}"

stop_pid_file() {
  local pid_file="$1"
  local label="$2"

  if [[ ! -f "$pid_file" ]]; then
    echo "[stop] No $label pid file found at $pid_file"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if [[ -z "$pid" ]]; then
    echo "[stop] Empty $label pid file"
    rm -f "$pid_file"
    return
  fi

  if kill -0 "$pid" >/dev/null 2>&1; then
    echo "[stop] Stopping local $label pid=$pid"
    kill "$pid" >/dev/null 2>&1 || true
    wait "$pid" 2>/dev/null || true
  else
    echo "[stop] $label pid=$pid is not running"
  fi

  rm -f "$pid_file"
}

stop_docker_stack() {
  if [[ ! -d "$BJJ_APP_DIR" || ! -f "$BJJ_APP_DIR/docker-compose.yml" ]]; then
    echo "[stop] BJJ app directory not available: $BJJ_APP_DIR"
    return
  fi

  if [[ "$REMOVE_DOCKER" == "true" ]]; then
    echo "[stop] Removing docker compose stack"
    (
      cd "$BJJ_APP_DIR"
      docker compose down
    )
    return
  fi

  if [[ "$STOP_DOCKER" == "true" ]]; then
    echo "[stop] Stopping docker compose services"
    (
      cd "$BJJ_APP_DIR"
      docker compose stop postgres backend frontend
    )
  fi
}

stop_pid_file "$AI_PID_FILE" "ai-service"
stop_pid_file "$FRONTEND_PID_FILE" "frontend"
stop_pid_file "$POC_YOLO_PID_FILE" "poc-yolo"
stop_pid_file "$POC_SPRING_PID_FILE" "poc-spring"

if [[ "$FORCE_PORT_CLEANUP" == "true" ]]; then
  echo "[stop] Force cleaning ports $AI_PORT, $FRONTEND_PORT, $POC_YOLO_PORT and $POC_SPRING_PORT"
  fuser -k "${AI_PORT}/tcp" >/dev/null 2>&1 || true
  fuser -k "${FRONTEND_PORT}/tcp" >/dev/null 2>&1 || true
  fuser -k "${POC_YOLO_PORT}/tcp" >/dev/null 2>&1 || true
  fuser -k "${POC_SPRING_PORT}/tcp" >/dev/null 2>&1 || true
fi

stop_docker_stack

echo "[stop] Stack stop sequence completed"
