#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.parity.yml}"

cd "$ROOT_DIR"

docker compose -f "$COMPOSE_FILE" up -d --build

echo "[ready] docker parity stack started"
echo "frontend:   http://localhost:3000"
echo "backend:    http://localhost:8080"
echo "ai-service: http://localhost:8081/health"
echo "spring-poc: http://localhost:8090/api/videos"
echo "yolo-poc:   http://localhost:8091/health"
