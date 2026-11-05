from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import httpx
import uuid
try:
    from ..config import settings
    from ..services.service_discovery import service_registry
except ImportError:
    from config import settings
    from services.service_discovery import service_registry

router = APIRouter(prefix="/api/v1/ingest", tags=["Data Ingestion"])

class IngestJobRequest(BaseModel):
    source_id: str = Field(..., examples=["s3://ai-data-lake/raw/train_set_v1.csv"])
    format: str = Field("CSV", examples=["CSV"])
    metadata: Dict[str, str] = Field(default_factory=dict)
    schema_id: Optional[str] = None
    data_payload: Optional[str] = None

class IngestJobResponse(BaseModel):
    job_id: str
    status: str
    records_processed: int
    errors: List[str] = Field(default_factory=list)

# In-memory mock store for fast gateway dispatch & proxying
_in_memory_jobs: Dict[str, Dict[str, Any]] = {}

@router.post("", response_model=IngestJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_ingestion(req: IngestJobRequest):
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    record_count = 1000 if not req.data_payload else len(req.data_payload.splitlines())

    job_data = {
        "job_id": job_id,
        "status": "PROCESSING",
        "records_processed": record_count,
        "format": req.format,
        "source_id": req.source_id,
        "errors": []
    }
    _in_memory_jobs[job_id] = job_data

    return IngestJobResponse(
        job_id=job_id,
        status="PROCESSING",
        records_processed=record_count,
        errors=[]
    )

@router.get("/{job_id}", response_model=IngestJobResponse)
async def get_ingestion_status(job_id: str):
    if job_id not in _in_memory_jobs:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    data = _in_memory_jobs[job_id]
    return IngestJobResponse(**data)

@router.post("/{job_id}/validate")
async def validate_job_data(job_id: str):
    if job_id not in _in_memory_jobs:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return {
        "job_id": job_id,
        "valid": True,
        "validation_errors": []
    }
