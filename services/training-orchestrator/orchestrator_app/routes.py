from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
try:
    from .orchestrator import orchestrator_instance
except ImportError:
    from orchestrator import orchestrator_instance

router = APIRouter(tags=["Training Orchestration"])

class JobSubmitRequest(BaseModel):
    model_type: str = Field(..., example="resnet50")
    dataset_id: str = Field(..., example="imagenet-mini")
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(5, ge=1, le=10)
    required_gpu: int = Field(1, ge=0)
    required_cpu: float = Field(4.0, ge=1.0)
    required_memory_gb: float = Field(16.0, ge=2.0)

class JobResponse(BaseModel):
    job_id: str
    model_type: str
    dataset_id: str
    priority: int
    status: str
    progress: float
    assigned_node: Optional[str] = None
    metrics: Dict[str, float] = Field(default_factory=dict)
    retries: int = 0

@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_job(req: JobSubmitRequest):
    job = await orchestrator_instance.submit_job(
        model_type=req.model_type,
        dataset_id=req.dataset_id,
        hyperparameters=req.hyperparameters,
        priority=req.priority,
        req_cpu=req.required_cpu,
        req_mem=req.required_memory_gb,
        req_gpu=req.required_gpu,
    )
    return JobResponse(
        job_id=job.job_id,
        model_type=job.model_type,
        dataset_id=job.dataset_id,
        priority=job.priority,
        status=job.status,
        progress=job.progress,
        assigned_node=job.assigned_node,
        metrics=job.metrics,
        retries=job.retries
    )

@router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(status_filter: Optional[str] = None):
    res = []
    for j in orchestrator_instance.jobs.values():
        if status_filter and j.status != status_filter:
            continue
        res.append(JobResponse(
            job_id=j.job_id,
            model_type=j.model_type,
            dataset_id=j.dataset_id,
            priority=j.priority,
            status=j.status,
            progress=j.progress,
            assigned_node=j.assigned_node,
            metrics=j.metrics,
            retries=j.retries
        ))
    return res

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str):
    if job_id not in orchestrator_instance.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    j = orchestrator_instance.jobs[job_id]
    return JobResponse(
        job_id=j.job_id,
        model_type=j.model_type,
        dataset_id=j.dataset_id,
        priority=j.priority,
        status=j.status,
        progress=j.progress,
        assigned_node=j.assigned_node,
        metrics=j.metrics,
        retries=j.retries
    )

@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_job(job_id: str):
    success = await orchestrator_instance.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or already finished")
    return None

@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: str):
    success = await orchestrator_instance.retry_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Job cannot be retried")
    j = orchestrator_instance.jobs[job_id]
    return JobResponse(
        job_id=j.job_id,
        model_type=j.model_type,
        dataset_id=j.dataset_id,
        priority=j.priority,
        status=j.status,
        progress=j.progress,
        assigned_node=j.assigned_node,
        metrics=j.metrics,
        retries=j.retries
    )

@router.get("/nodes")
async def list_compute_nodes():
    return orchestrator_instance.balancer.list_nodes()
