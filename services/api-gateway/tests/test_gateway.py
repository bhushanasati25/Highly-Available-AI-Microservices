import pytest
from httpx import AsyncClient, ASGITransport
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../shared/python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gateway_app.main import app

@pytest.mark.asyncio
async def test_health_and_kubernetes_probes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Legacy /health
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"

        # K8s Liveness Probe /healthz
        res_live = await client.get("/healthz")
        assert res_live.status_code == 200
        assert res_live.json()["status"] == "alive"

        # K8s Readiness Probe /readyz
        res_ready = await client.get("/readyz")
        assert res_ready.status_code == 200
        assert res_ready.json()["status"] == "ready"

        # K8s Startup Probe /startupz
        res_startup = await client.get("/startupz")
        assert res_startup.status_code == 200
        assert res_startup.json()["status"] == "started"

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
