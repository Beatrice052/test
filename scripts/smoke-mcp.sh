#!/usr/bin/env sh
set -eu
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec uv run --project "$PROJECT_ROOT/backend" python -m app.cli mcp smoke "$@"
