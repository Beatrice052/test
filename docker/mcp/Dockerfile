FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
RUN pip install --no-cache-dir uv
COPY docker/mcp/pyproject.toml docker/mcp/uv.lock ./
RUN uv sync --frozen --no-dev

EXPOSE 9900
CMD ["uv", "run", "python", "-m", "mcp_server_opensearch", "--transport", "stream", "--host", "0.0.0.0", "--port", "9900", "--log-format", "json"]
