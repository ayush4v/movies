"""Unit tests for FastAPI healthcheck and webhook endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from app.api.server import create_api_app
from app.config import Settings


@pytest.mark.asyncio
async def test_health_check_endpoint():
    app = create_api_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "uptime_seconds" in data
    assert "components" in data
    assert "database" in data["components"]
    assert "storage_provider" in data["components"]


@pytest.mark.asyncio
async def test_storage_webhook():
    app = create_api_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/webhook/storage", json={"event": "file_uploaded", "file_id": "123"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["event"] == "file_uploaded"
