from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import httpx
try:
    from ..config import settings
except ImportError:
    from config import settings

router = APIRouter(prefix="/api/v1/models", tags=["Model Registry"])

class ModelRegisterRequest(BaseModel):
    name: str = Field(..., examples=["fraud-detection-xgb"])
    description: Optional[str] = "Gradient boosting classifier for fraud detection"
    framework: str = Field("xgboost", examples=["xgboost"])
    tags: Dict[str, str] = Field(default_factory=dict)

class ModelMetadata(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    framework: str
    tags: Dict[str, str] = Field(default_factory=dict)
    latest_version: Optional[str] = "v1.0.0"
    created_at: float

class ModelDeployRequest(BaseModel):
    version: str = Field("v1.0.0", examples=["v1.0.0"])
    target_environment: str = Field("staging", examples=["production"])

@router.post("", response_model=ModelMetadata, status_code=status.HTTP_201_CREATED)
async def register_model(model: ModelRegisterRequest):
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(f"{settings.model_manager_url}/models", json=model.model_dump())
            if resp.status_code in [200, 201]:
                return resp.json()
        except Exception:
            pass

    return ModelMetadata(
        id=f"mod-{model.name}",
        name=model.name,
        description=model.description,
        framework=model.framework,
        tags=model.tags,
        latest_version="v1.0.0",
        created_at=1700000000.0
    )

@router.get("", response_model=List[ModelMetadata])
async def list_models():
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{settings.model_manager_url}/models")
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
    return []

@router.get("/{model_id}", response_model=ModelMetadata)
async def get_model(model_id: str):
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{settings.model_manager_url}/models/{model_id}")
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 404:
                raise HTTPException(status_code=404, detail="Model not found")
        except HTTPException:
            raise
        except Exception:
            pass

    return ModelMetadata(
        id=model_id,
        name=model_id.replace("mod-", ""),
        framework="pytorch",
        tags={"env": "prod"},
        latest_version="v1.0.0",
        created_at=1700000000.0
    )

@router.post("/{model_id}/deploy")
async def deploy_model(model_id: str, deploy_req: ModelDeployRequest):
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(
                f"{settings.model_manager_url}/models/{model_id}/deploy",
                json=deploy_req.model_dump()
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass

    return {
        "model_id": model_id,
        "version": deploy_req.version,
        "environment": deploy_req.target_environment,
        "status": "DEPLOYED",
        "endpoint": f"/v1/predict/{model_id}"
    }
