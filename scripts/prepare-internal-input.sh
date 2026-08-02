#!/usr/bin/env sh
set -eu
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec uv run --project "$PROJECT_ROOT/backend" python \
  "$PROJECT_ROOT/scripts/prepare_internal_input.py" "$@"
