"""FastAPI entry point: `uv run uvicorn apps.api.main:app --reload`."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response, status
from sqlalchemy.orm import Session, sessionmaker

from apps.api import errors
from apps.api.auth.tokens import JwtSigner
from apps.api.db.session import make_engine, make_session_factory
from apps.api.health import check_dependencies
from apps.api.routers import auth, bugs, cases, costs, graph, pipeline, plans, projects
from apps.api.settings import Settings, get_settings
from apps.api.storage import ObjectStore, S3ObjectStore
from apps.api.trackers import TrackerFactory, tracker_factory

API_PREFIX = "/api/v1"

# docs/10-authentication-and-security.md §7
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' blob: data:; frame-src 'self'; connect-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    ),
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def _signer(settings: Settings) -> JwtSigner:
    if settings.jwt_private_key is not None:
        return JwtSigner.from_pem(settings.jwt_private_key.get_secret_value())
    if settings.saq_env == "prod":
        raise RuntimeError("JWT_PRIVATE_KEY (Ed25519 PEM) is required when SAQ_ENV=prod")
    return JwtSigner.ephemeral()


def _store(settings: Settings) -> ObjectStore | None:
    if not (settings.s3_endpoint and settings.s3_access_key and settings.s3_secret_key):
        return None
    return S3ObjectStore.from_settings(
        settings.s3_endpoint,
        settings.s3_bucket,
        settings.s3_access_key,
        settings.s3_secret_key.get_secret_value(),
    )


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    jwt_signer: JwtSigner | None = None,
    object_store: ObjectStore | None = None,
    trackers: TrackerFactory | None = None,
) -> FastAPI:
    """Build the FastAPI application. Tests inject a session factory and signer."""
    settings = get_settings()
    app = FastAPI(
        title="Smart Autonomous QA API",
        version="0.1.0",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
    )
    if session_factory is None and settings.database_url:
        session_factory = make_session_factory(make_engine(settings.database_url))
    app.state.session_factory = session_factory
    app.state.jwt_signer = jwt_signer or _signer(settings)
    app.state.object_store = object_store or _store(settings)
    app.state.tracker_factory = trackers or tracker_factory(settings)
    errors.install(app)

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(projects.router, prefix=API_PREFIX)
    app.include_router(pipeline.router, prefix=API_PREFIX)
    app.include_router(costs.router, prefix=API_PREFIX)
    app.include_router(graph.router, prefix=API_PREFIX)
    app.include_router(plans.router, prefix=API_PREFIX)
    app.include_router(cases.router, prefix=API_PREFIX)
    app.include_router(bugs.router, prefix=API_PREFIX)

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
