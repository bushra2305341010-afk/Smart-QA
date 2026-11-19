"""Error envelope for every API failure (docs/06-api.md §2).

{"error": {"code": "FORBIDDEN", "message": "...", "details": {...}, "trace_id": "..."}}
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """Raise anywhere in a request to return a structured error."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}
        self.headers = headers


def unauthenticated(message: str = "Sign in required") -> ApiError:
    return ApiError(401, "UNAUTHENTICATED", message)


def forbidden(permission: str) -> ApiError:
    return ApiError(403, "FORBIDDEN", "Your role lacks this permission", {"permission": permission})


def not_found(what: str) -> ApiError:
    """Also used when the resource exists in a project you cannot see (no existence leak)."""
    return ApiError(404, "NOT_FOUND", f"{what} not found")


def conflict(message: str, code: str = "STATE_CONFLICT") -> ApiError:
    return ApiError(409, code, message)


def _body(code: str, message: str, details: dict[str, Any]) -> dict[str, Any]:
    trace_id = uuid.uuid4().hex
    return {"error": {"code": code, "message": message, "details": details, "trace_id": trace_id}}


_HTTP_CODES = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "NOT_FOUND"}


def install(app: FastAPI) -> None:
    """Register handlers so every error uses the envelope."""

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            _body(exc.code, exc.message, exc.details), exc.status, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(
            _body("VALIDATION_ERROR", "Request is invalid", {"fields": fields}), 400
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "VALIDATION_ERROR")
        return JSONResponse(_body(code, str(exc.detail), {}), exc.status_code)
