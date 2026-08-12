FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# --frozen: install exactly what's in uv.lock, ignore whatever pyproject.toml
# would otherwise re-resolve to. Keeps the image immune to future PyPI
# releases regardless of the version pin in pyproject.toml.
RUN uv sync --frozen --no-dev

EXPOSE 8000

# Render injects $PORT; the SURF VM / docker-compose don't, so fall back to
# DUCKLAKE_MCP_PORT (or 8000) when it's unset.
CMD ["sh", "-c", "DUCKLAKE_MCP_PORT=${PORT:-${DUCKLAKE_MCP_PORT:-8000}} DUCKLAKE_MCP_TRANSPORT=streamable-http uv run ori-ducklake-mcp"]
