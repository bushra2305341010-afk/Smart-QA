"""FastAPI entry point: `uv run uvicorn apps.api.main:app --reload`."""

from __future__ import annotations

from fastapi import FastAPI, Response, status

from apps.api.health import check_dependencies
from apps.api.settings import get_settings

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    app = FastAPI(
        title="Smart Autonomous QA API",
        version="0.1.0",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
    )

    @app.get(f"{API_PREFIX}/healthz", tags=["ops"])
    async def healthz() -> dict[str, str]:
        """Liveness: the process is up."""
        return {"status": "ok"}

    @app.get(f"{API_PREFIX}/readyz", tags=["ops"])
    async def readyz(response: Response) -> dict[str, object]:
        """Readiness: configured dependencies (DB, Redis) are reachable."""
        settings = get_settings()
        results = await check_dependencies(
            {"database": settings.database_url, "redis": settings.redis_url}
        )
        ready = all(r.ok for r in results)
        if not ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "ready" if ready else "not_ready",
            "dependencies": {r.name: r.detail for r in results},
        }

    return app


app = create_app()
