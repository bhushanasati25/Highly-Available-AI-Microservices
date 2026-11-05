import pytest
from httpx import AsyncClient, ASGITransport
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../shared/python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orchestrator_app.main import app

@pytest.mark.asyncio
async def test_training_orchestrator_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_job_submission_and_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "model_type": "bert-base-uncased",
            "dataset_id": "glue-sst2",
            "hyperparameters": {"lr": 2e-5, "epochs": 3},
            "priority": 8,
            "required_gpu": 1,
            "required_cpu": 4.0,
            "required_memory_gb": 16.0
        }
        submit_resp = await client.post("/jobs", json=payload)
        assert submit_resp.status_code == 202
        job_data = submit_resp.json()
        job_id = job_data["job_id"]
        assert job_id.startswith("train-")

        # Query job
        get_resp = await client.get(f"/jobs/{job_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["model_type"] == "bert-base-uncased"

@pytest.mark.asyncio
async def test_compute_nodes_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/nodes")
        assert resp.status_code == 200
        nodes = resp.json()
        assert len(nodes) >= 10
