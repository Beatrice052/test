#!/usr/bin/env sh
set -eu
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec uv run --project "$PROJECT_ROOT/backend" python \
  "$PROJECT_ROOT/scripts/build_shadow_report.py" "$@"
