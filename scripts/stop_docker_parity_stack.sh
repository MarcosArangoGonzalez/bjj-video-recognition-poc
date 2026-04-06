#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.parity.yml}"

cd "$ROOT_DIR"

docker compose -f "$COMPOSE_FILE" down

echo "[stop] docker parity stack stopped"
