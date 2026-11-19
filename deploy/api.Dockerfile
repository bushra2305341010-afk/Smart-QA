FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY apps ./apps
COPY packages ./packages
COPY alembic.ini ./
RUN uv sync --frozen --no-dev
RUN useradd --create-home --uid 10001 saq
USER saq
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
