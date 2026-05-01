"""FastAPI application entry point.

Wires up:
  - structured logging
  - DB pool lifecycle
  - request_id middleware (for log correlation)
  - consistent JSON error handler
  - all routes (/health, /ready, /ingest, /ask, /search)
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.routes import router
from app.config import get_settings
from app.db import close_pool, init_pool
from app.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
)

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    log.info("app.startup", env=settings.app_env, version=__version__)

    # DB pool: required. If it can't be reached we still start so /health
    # answers, but /ready will fail until the DB comes up.
    try:
        await init_pool()
    except Exception as e:  # noqa: BLE001
        log.error("app.startup.db_pool_failed", error=str(e))

    yield

    await close_pool()
    log.info("app.shutdown")


app = FastAPI(
    title="regrag",
    description="RAG over Indian financial regulatory documents (SEBI + RBI).",
    version=__version__,
    lifespan=lifespan,
)


# ---------- middleware ----------

# CORS — the web frontend lives on a different origin (localhost:3000) and
# cannot reach the API from the browser without an explicit allowlist.
_settings = get_settings()
_allow_origins = [
    o.strip() for o in _settings.cors_allow_origins.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["x-request-id"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next: Any) -> Any:
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    bind_request_context(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("request.unhandled_error")
        clear_request_context()
        raise
    duration_ms = int((time.perf_counter() - start) * 1000)
    response.headers["x-request-id"] = request_id
    log.info(
        "request.completed",
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    clear_request_context()
    return response


# ---------- error handlers ----------


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail}},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": 422,
                "message": "validation_failed",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
    log.exception("internal_server_error", error_type=type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": 500, "message": "internal_server_error"}},
    )


# ---------- routes ----------

app.include_router(router)
