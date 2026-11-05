import pytest
from httpx import AsyncClient, ASGITransport
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../shared/python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gateway_app.main import app

@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "api-gateway"

@pytest.mark.asyncio
async def test_auth_token_generation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/token?username=testuser")
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_ingest_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "source_id": "s3://test-bucket/data.csv",
            "format": "CSV",
            "data_payload": "f1,f2\n1.0,2.0\n3.0,4.0"
        }
        resp = await client.post("/api/v1/ingest", json=payload)
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        status_resp = await client.get(f"/api/v1/ingest/{job_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["job_id"] == job_id

@pytest.mark.asyncio
async def test_dashboard_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/dashboard")
        assert resp.status_code == 200
        assert "Highly Available AI Microservices" in resp.text
        assert "50-Node Distributed Cluster Topology Map" in resp.text
