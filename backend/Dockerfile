FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    APP_ENV=mock \
    APP_DATABASE_URL=sqlite:///./var/chatbi.db \
    APP_CHECKPOINT_PATH=./var/checkpoints.db \
    APP_ARTIFACT_DIR=./var/artifacts \
    CHATBI_SEMANTIC_PACKAGE_DIR=../compiled-semantic/mock \
    CHATBI_LLM_FIXTURE_PATH=../fixtures/llm/analysis_plans.json

WORKDIR /app/backend
RUN pip install --no-cache-dir uv
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY compiled-semantic/mock /app/compiled-semantic/mock
COPY config /app/config
COPY fixtures /app/fixtures
COPY scripts /app/scripts
COPY semantic-input /app/semantic-input

EXPOSE 8000
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
