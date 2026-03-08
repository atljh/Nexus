#!/bin/bash

# Nexus Release Validation Script
# Usage: ./scripts/release-check.sh [mac|win]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TARGET="${1:-mac}"

resolve_backend_entry() {
  local base="$PROJECT_DIR/backend-dist/main"
  local candidates=(
    "$base/main"
    "$base/main.exe"
    "$base"
    "$base.exe"
  )
  local candidate=""

  for candidate in "${candidates[@]}"; do
    if [ -x "$candidate" ] && [ ! -d "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

LOG_FILE="/tmp/nexus_release_backend_$$.log"
HEALTH_FILE="/tmp/nexus_release_health_$$.out"
BACKEND_PID=""

cleanup() {
  if [ -n "${BACKEND_PID:-}" ]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    pkill -P "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

echo "[1/7] Lint"
cd "$PROJECT_DIR"
pnpm lint

echo "[2/7] Typecheck"
pnpm typecheck

echo "[3/7] Backend tests"
cd "$PROJECT_DIR/backend"
./.venv/bin/pytest -q

echo "[4/7] Task flow smoke"
cd "$PROJECT_DIR"
./scripts/task-flow-check.py

echo "[5/7] Build ($TARGET)"
cd "$PROJECT_DIR"
./scripts/build.sh "$TARGET"

echo "[6/7] Smoke test packaged backend"
if ! BACKEND_ENTRY="$(resolve_backend_entry)"; then
  echo "ERROR: backend executable not found in $PROJECT_DIR/backend-dist/main"
  exit 1
fi

if [ ! -x "$BACKEND_ENTRY" ]; then
  echo "ERROR: backend executable not found: $BACKEND_ENTRY"
  exit 1
fi

"$BACKEND_ENTRY" > "$LOG_FILE" 2>&1 &
BACKEND_PID=$!

HEALTH_OK=0
for i in {1..40}; do
  if python3 - <<'PY' > "$HEALTH_FILE" 2>/dev/null
import sys
from urllib.request import urlopen

with urlopen("http://127.0.0.1:8000/health", timeout=1.5) as resp:
    if resp.status != 200:
        raise SystemExit(1)
    sys.stdout.write(resp.read().decode("utf-8", errors="replace"))
PY
  then
    HEALTH_OK=1
    echo "Backend healthy in ${i}s"
    break
  fi
  sleep 1
done

cleanup
BACKEND_PID=""

if [ "$HEALTH_OK" -ne 1 ]; then
  echo "ERROR: packaged backend health check failed"
  echo "--- backend log ---"
  tail -n 80 "$LOG_FILE" || true
  exit 1
fi

echo "[7/7] Artifacts"
ls -lah "$PROJECT_DIR/release" | sed -n '1,20p'

echo "Release validation completed successfully."
