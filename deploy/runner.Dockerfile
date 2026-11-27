# Runner (sector 05): runs inside the team network, calls the control plane outbound only.
# Each job gets a fresh browser context; run one container per runner, no privileged mode.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv
WORKDIR /app
# libatomic1: needed by the Node driver bundled with Playwright (browser deps come from --with-deps)
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY apps ./apps
COPY packages ./packages
COPY evals/fixtures ./evals/fixtures
RUN uv sync --frozen --no-dev \
    && /app/.venv/bin/playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10002 runner && mkdir -p /vault && chown runner /vault
USER runner
CMD ["/app/.venv/bin/python", "-m", "apps.runner"]
