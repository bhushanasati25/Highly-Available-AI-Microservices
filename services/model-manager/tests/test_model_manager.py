import pytest
from httpx import AsyncClient, ASGITransport
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../shared/python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from model_app.main import app

@pytest.mark.asyncio
async def test_model_manager_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_register_and_promote_model():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register model
        payload = {
            "name": "vision-transformer",
            "framework": "pytorch",
            "description": "ViT-B/16 image backbone",
            "tags": {"domain": "vision"}
        }
        create_resp = await client.post("/models", json=payload)
        assert create_resp.status_code == 201
        model_id = create_resp.json()["id"]

        # 2. Add version v1.1.0
        v_payload = {
            "version_id": "v1.1.0",
            "metrics": {"top1_acc": 0.84},
            "changelog": "Fine-tuned on domain data"
        }
        v_resp = await client.post(f"/models/{model_id}/versions", json=v_payload)
        assert v_resp.status_code == 201
        assert v_resp.json()["version_id"] == "v1.1.0"

        # 3. Deploy version to production
        deploy_payload = {
            "version": "v1.1.0",
            "target_environment": "production"
        }
        deploy_resp = await client.post(f"/models/{model_id}/deploy", json=deploy_payload)
        assert deploy_resp.status_code == 200
        assert deploy_resp.json()["stage"] == "production"
        assert "artifact_url" in deploy_resp.json()
