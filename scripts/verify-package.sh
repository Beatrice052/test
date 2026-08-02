#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
VERIFY_DIR="$PROJECT_ROOT/.cache/verify-package"
mkdir -p "$VERIFY_DIR"

for command_name in uv node npm npx; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "Required command is missing: $command_name" >&2
    exit 1
  }
done

NODE_MAJOR=$(node --version | sed 's/^v//' | cut -d. -f1)
[ "$NODE_MAJOR" = "22" ] || {
  echo "Node.js 22 LTS is required; detected $(node --version)." >&2
  exit 1
}

export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$PROJECT_ROOT/.cache/uv-python"
export npm_config_cache="$PROJECT_ROOT/.cache/npm"

cleanup() {
  [ -z "${UI_PID:-}" ] || kill "$UI_PID" 2>/dev/null || true
  [ -z "${BACKEND_PID:-}" ] || kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

(cd "$BACKEND_DIR" && uv sync --all-groups --locked)
(cd "$BACKEND_DIR" && uv run ruff check app tests migrations ../scripts)
(cd "$BACKEND_DIR" && uv run ruff format --check app tests migrations ../scripts)
(cd "$BACKEND_DIR" && uv run mypy app)
(cd "$BACKEND_DIR" && uv run pytest -q)
uv run --project "$BACKEND_DIR" python "$PROJECT_ROOT/scripts/check_schema_snapshots.py"
uv run --project "$BACKEND_DIR" python "$PROJECT_ROOT/scripts/generate_frontend_types.py" --check
uv run --project "$BACKEND_DIR" python -m app.cli semantic compile \
  --input-dir "$PROJECT_ROOT/semantic-input/mock" \
  --output-dir "$VERIFY_DIR/compiled-semantic"

(cd "$FRONTEND_DIR" && npm ci)
(cd "$FRONTEND_DIR" && npm run typecheck)
(cd "$FRONTEND_DIR" && npm run lint)
(cd "$FRONTEND_DIR" && npm run test -- --run)
(cd "$FRONTEND_DIR" && npm run build)
(cd "$FRONTEND_DIR" && npx playwright install chromium)
(cd "$FRONTEND_DIR" && "$BACKEND_DIR/.venv/bin/python" -m http.server 4173 \
  --bind 127.0.0.1 --directory dist \
  >"$VERIFY_DIR/frontend.stdout.log" 2>"$VERIFY_DIR/frontend.stderr.log") &
UI_PID=$!
uv run --project "$BACKEND_DIR" python "$PROJECT_ROOT/scripts/wait_http.py" \
  http://127.0.0.1:4173 --timeout-seconds 20
(cd "$FRONTEND_DIR" && npx playwright test --reporter=line)
kill "$UI_PID" 2>/dev/null || true
unset UI_PID

export APP_ENV=verify-mock
export APP_DATABASE_URL="sqlite:///$VERIFY_DIR/chatbi.db"
export APP_ARTIFACT_DIR="$VERIFY_DIR/artifacts"
export APP_CHECKPOINT_PATH="$VERIFY_DIR/checkpoints.db"
export CHATBI_SEMANTIC_PACKAGE_DIR="$VERIFY_DIR/compiled-semantic"
export CHATBI_LLM_MODE=rule_based
export CHATBI_GATEWAY_MODE=mock

(cd "$BACKEND_DIR" && uv run uvicorn app.main:app --host 127.0.0.1 --port 18000 \
  >"$VERIFY_DIR/backend.stdout.log" 2>"$VERIFY_DIR/backend.stderr.log") &
BACKEND_PID=$!
uv run --project "$BACKEND_DIR" python "$PROJECT_ROOT/scripts/wait_http.py" \
  http://127.0.0.1:18000/api/v1/health/ready --timeout-seconds 30

echo "PACKAGE VERIFICATION PASSED: lockfiles, Semantic, backend, frontend, G01-G25, Playwright, and Mock readiness."
