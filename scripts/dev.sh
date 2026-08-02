#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

command -v uv >/dev/null 2>&1 || { echo "Required command is missing: uv" >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Required command is missing: node" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "Required command is missing: npm" >&2; exit 1; }

REQUIRED_NODE=$(tr -d '\r\n ' < "$PROJECT_ROOT/.node-version")
ACTUAL_NODE=$(node --version | sed 's/^v//')
[ "$ACTUAL_NODE" = "$REQUIRED_NODE" ] || {
  echo "Node.js $REQUIRED_NODE is required; detected $ACTUAL_NODE." >&2
  exit 1
}

export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$PROJECT_ROOT/.cache/uv-python"
export npm_config_cache="$PROJECT_ROOT/.cache/npm"
export APP_ENV=local
export CHATBI_IDENTITY_MODE=mock
export CHATBI_LLM_MODE=rule_based
export CHATBI_GATEWAY_MODE=mock

(cd "$BACKEND_DIR" && uv sync --all-groups --locked)
(cd "$PROJECT_ROOT" && uv run --project backend python -m app.cli semantic compile --input-dir semantic-input/mock --output-dir compiled-semantic/mock)
(cd "$BACKEND_DIR" && uv run alembic upgrade head)
(cd "$FRONTEND_DIR" && npm ci)

cleanup() {
  [ -z "${BACKEND_PID:-}" ] || kill "$BACKEND_PID" 2>/dev/null || true
  [ -z "${FRONTEND_PID:-}" ] || kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

(cd "$BACKEND_DIR" && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!
(cd "$FRONTEND_DIR" && npm run dev -- --host 127.0.0.1 --port 5173) &
FRONTEND_PID=$!

echo "Backend: http://127.0.0.1:8000"
echo "Frontend: http://127.0.0.1:5173"
uv run --project "$BACKEND_DIR" python "$PROJECT_ROOT/scripts/wait_http.py" \
  http://127.0.0.1:8000/api/v1/health/ready --timeout-seconds 30
uv run --project "$BACKEND_DIR" python "$PROJECT_ROOT/scripts/wait_http.py" \
  http://127.0.0.1:5173 --timeout-seconds 30

while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done
echo "A development service stopped unexpectedly." >&2
exit 1
