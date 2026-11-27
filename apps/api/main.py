"""FastAPI entry point: `uv run uvicorn apps.api.main:app --reload`."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, sessionmaker

from apps.api import errors
from apps.api.auth.breached import BreachChecker, NoCheck, OfflineChecker, OnlineChecker
from apps.api.auth.tokens import JwtSigner
from apps.api.crypto import SecretBox
from apps.api.db.session import make_engine, make_session_factory
from apps.api.health import check_dependencies
from apps.api.ratelimit import MemoryRateLimiter, RateLimiter, RedisRateLimiter
from apps.api.routers import (
    auth,
    bugs,
    cases,
    costs,
    graph,
    learning,
    pipeline,
    plans,
    projects,
    runners,
    runs,
)
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

# The interactive API docs page loads Swagger UI from jsDelivr and starts it with an inline
# script, which the strict policy above blocks (blank page). Only that page gets this policy;
# it shows no user content.
SWAGGER_CDN = "https://cdn.jsdelivr.net"
DOCS_CSP = (
    f"default-src 'self'; script-src 'self' 'unsafe-inline' {SWAGGER_CDN}; "
    f"style-src 'self' 'unsafe-inline' {SWAGGER_CDN}; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
)

# Shown on the docs page's "Authorize" dialog. Browser sign-in sets an access cookie; requests
# that change state also need the CSRF token returned by /auth/login. Scripts use API tokens.
SECURITY_SCHEMES = {
    "csrf": {
        "type": "apiKey",
        "in": "header",
        "name": "X-CSRF-Token",
        "description": "After POST /auth/login in this page, paste the returned csrf_token.",
    },
    "bearer": {
        "type": "http",
        "scheme": "bearer",
        "description": "An API token (saq_pat_...) from POST /auth/tokens.",
    },
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


def _limiter(settings: Settings) -> RateLimiter:
    if settings.rate_limit_backend == "redis" and settings.redis_url:
        import redis

        return RedisRateLimiter(redis.Redis.from_url(settings.redis_url))
    return MemoryRateLimiter()


def _breach(settings: Settings) -> BreachChecker:
    if settings.breach_check_mode == "online":
        return OnlineChecker()
    if settings.breach_check_mode == "offline":
        if not settings.breach_hash_file:
            raise RuntimeError("BREACH_HASH_FILE is required for offline checks")
        return OfflineChecker(Path(settings.breach_hash_file))
    return NoCheck()


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    jwt_signer: JwtSigner | None = None,
    object_store: ObjectStore | None = None,
    trackers: TrackerFactory | None = None,
    rate_limiter: RateLimiter | None = None,
    breach_checker: BreachChecker | None = None,
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
    app.state.rate_limiter = rate_limiter or _limiter(settings)
    app.state.breach_checker = breach_checker or _breach(settings)
    app.state.secret_box = (
        SecretBox.from_b64(settings.saq_encryption_key.get_secret_value())
        if settings.saq_encryption_key
        else None
    )
    errors.install(app)

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        if request.url.path == app.docs_url:
            response.headers["Content-Security-Policy"] = DOCS_CSP
        return response

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
            schema.setdefault("components", {})["securitySchemes"] = SECURITY_SCHEMES
            schema["security"] = [{"csrf": []}, {"bearer": []}]
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]

    @app.get("/", include_in_schema=False)
    @app.get("/docs", include_in_schema=False)
    async def to_docs() -> RedirectResponse:
        return RedirectResponse(f"{API_PREFIX}/docs")

    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(projects.router, prefix=API_PREFIX)
    app.include_router(pipeline.router, prefix=API_PREFIX)
    app.include_router(costs.router, prefix=API_PREFIX)
    app.include_router(graph.router, prefix=API_PREFIX)
    app.include_router(plans.router, prefix=API_PREFIX)
    app.include_router(cases.router, prefix=API_PREFIX)
    app.include_router(bugs.router, prefix=API_PREFIX)
    app.include_router(learning.router, prefix=API_PREFIX)
    app.include_router(runners.router, prefix=API_PREFIX)
    app.include_router(runs.router, prefix=API_PREFIX)

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
