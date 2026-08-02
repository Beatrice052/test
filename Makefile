.PHONY: backend-check frontend-check test dev

backend-check:
	cd backend && uv sync --all-groups --locked && uv run ruff check app tests migrations ../scripts && uv run ruff format --check app tests migrations ../scripts && uv run mypy app && uv run pytest -q

frontend-check:
	cd frontend && npm ci && npm run lint && npm run typecheck && npm run test -- --run && npm run build

test: backend-check frontend-check

dev:
	./scripts/dev.sh

verify:
	./scripts/verify-package.sh
