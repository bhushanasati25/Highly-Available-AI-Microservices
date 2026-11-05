import pytest
from httpx import AsyncClient, ASGITransport
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../shared/python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitoring_app.main import app

@pytest.mark.asyncio
async def test_monitoring_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_heartbeat_post_and_cluster_status():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Send heartbeat
        hb = {"cpu_usage": 45.2, "memory_usage": 60.1, "gpu_available": 1}
        resp = await client.post("/nodes/worker-node-99/heartbeat", json=hb)
        assert resp.status_code == 200
        assert resp.json()["node_id"] == "worker-node-99"

        # Check cluster status
        stat_resp = await client.get("/status")
        assert stat_resp.status_code == 200
        assert stat_resp.json()["total_nodes_count"] >= 1
