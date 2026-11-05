from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
try:
    from .registry import registry_instance
except ImportError:
    from registry import registry_instance

router = APIRouter(tags=["Model Management"])

class CreateModelRequest(BaseModel):
    name: str = Field(..., example="bert-sentiment-classifier")
    framework: str = Field("pytorch", example="pytorch")
    description: str = Field("", example="Fine-tuned BERT model for multi-class sentiment analysis")
    tags: Dict[str, str] = Field(default_factory=dict)
    dataset_id: Optional[str] = None
    job_id: Optional[str] = None

class CreateVersionRequest(BaseModel):
    version_id: str = Field(..., example="v1.1.0")
    artifact_content_b64: Optional[str] = None
    metrics: Dict[str, float] = Field(default_factory=dict)
    changelog: str = Field("", example="Improved validation accuracy with learning rate warmup")

class DeployRequest(BaseModel):
    version: str = Field("v1.0.0", example="v1.0.0")
    target_environment: str = Field("production", example="production")

@router.post("/models", status_code=status.HTTP_201_CREATED)
async def register_model(req: CreateModelRequest):
    record = registry_instance.register_model(
        name=req.name,
        framework=req.framework,
        description=req.description,
        tags=req.tags,
        dataset_id=req.dataset_id,
        job_id=req.job_id
    )
    return {
        "id": record.id,
        "name": record.name,
        "framework": record.framework,
        "description": record.description,
        "tags": record.tags,
        "latest_version": "v1.0.0",
        "created_at": record.created_at
    }

@router.get("/models")
async def list_models():
    models = registry_instance.list_models()
    res = []
    for m in models:
        versions = registry_instance.versioning.list_versions(m.id)
        latest = versions[-1].version_id if versions else "v1.0.0"
        res.append({
            "id": m.id,
            "name": m.name,
            "framework": m.framework,
            "description": m.description,
            "tags": m.tags,
            "latest_version": latest,
            "created_at": m.created_at
        })
    return res

@router.get("/models/{model_id}")
async def get_model(model_id: str):
    m = registry_instance.get_model(model_id)
    if not m:
        raise HTTPException(status_code=404, detail="Model not found")
    versions = registry_instance.versioning.list_versions(m.id)
    latest = versions[-1].version_id if versions else "v1.0.0"
    return {
        "id": m.id,
        "name": m.name,
        "framework": m.framework,
        "description": m.description,
        "tags": m.tags,
        "latest_version": latest,
        "created_at": m.created_at
    }

@router.get("/models/{model_id}/versions")
async def list_model_versions(model_id: str):
    m = registry_instance.get_model(model_id)
    if not m:
        raise HTTPException(status_code=404, detail="Model not found")
    versions = registry_instance.versioning.list_versions(model_id)
    return [
        {
            "version_id": v.version_id,
            "artifact_sha": v.artifact_sha,
            "stage": v.stage,
            "metrics": v.metrics,
            "changelog": v.changelog,
            "created_at": v.created_at
        }
        for v in versions
    ]

@router.post("/models/{model_id}/versions", status_code=status.HTTP_201_CREATED)
async def create_model_version(model_id: str, req: CreateVersionRequest):
    m = registry_instance.get_model(model_id)
    if not m:
        raise HTTPException(status_code=404, detail="Model not found")

    content = (req.artifact_content_b64 or "dummy_weights").encode("utf-8")
    sha = registry_instance.artifact_store.store_artifact(f"{m.name}_{req.version_id}.bin", content)

    try:
        ver = registry_instance.versioning.create_version(
            model_id=model_id,
            version_id=req.version_id,
            artifact_sha=sha,
            metrics=req.metrics,
            changelog=req.changelog
        )
        return {
            "version_id": ver.version_id,
            "artifact_sha": ver.artifact_sha,
            "stage": ver.stage,
            "metrics": ver.metrics
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/models/{model_id}/deploy")
async def deploy_model(model_id: str, req: DeployRequest):
    m = registry_instance.get_model(model_id)
    if not m:
        raise HTTPException(status_code=404, detail="Model not found")

    ver = registry_instance.versioning.promote_version(model_id, req.version, req.target_environment)
    if not ver:
        raise HTTPException(status_code=404, detail="Version not found")

    download_url = registry_instance.artifact_store.generate_signed_download_url(ver.artifact_sha)
    return {
        "model_id": model_id,
        "version": ver.version_id,
        "stage": ver.stage,
        "status": "DEPLOYED",
        "artifact_url": download_url
    }
