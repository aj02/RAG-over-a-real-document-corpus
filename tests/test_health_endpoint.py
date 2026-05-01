"""Smoke test that the FastAPI app boots and /health responds without
touching the database or any external service.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Stub out lifespan side effects so importing app.main doesn't try to
    # open a DB pool during unit tests.
    from app import db
    from app import main as main_mod

    async def fake_init_pool() -> object:
        return None

    async def fake_close_pool() -> None:
        return None

    monkeypatch.setattr(db, "init_pool", fake_init_pool)
    monkeypatch.setattr(db, "close_pool", fake_close_pool)
    monkeypatch.setattr(main_mod, "init_pool", fake_init_pool)
    monkeypatch.setattr(main_mod, "close_pool", fake_close_pool)

    return TestClient(main_mod.app)


def test_health_returns_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_request_id_is_echoed(client: TestClient) -> None:
    resp = client.get("/health", headers={"x-request-id": "abc123"})
    assert resp.status_code == 200
    assert resp.headers.get("x-request-id") == "abc123"


def test_unauthenticated_ingest_rejected(client: TestClient) -> None:
    resp = client.post("/ingest", json={"force": False})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == 401
