"""FastAPI dependencies (auth, rate-limit, etc.)."""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.config import get_settings


def require_ingest_token(authorization: str | None = Header(default=None)) -> None:
    """Bearer-token gate for /ingest. Constant-time compare to avoid timing leaks."""
    settings = get_settings()
    expected = f"Bearer {settings.ingest_bearer_token}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
