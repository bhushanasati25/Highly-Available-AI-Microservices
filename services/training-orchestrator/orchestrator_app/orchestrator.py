import asyncio
import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import structlog

try:
    from .workload_balancer import WorkloadBalancer, ComputeNode
    from .job_scheduler import JobScheduler, QueuedJob
except ImportError:
    from workload_balancer import WorkloadBalancer, ComputeNode
    from job_scheduler import JobScheduler, QueuedJob

logger = structlog.get_logger(__name__)

@dataclass
class JobState:
    job_id: str
    model_type: str
    dataset_id: str
    hyperparameters: Dict[str, Any]
    priority: int = 5
    req_cpu: float = 4.0
    req_mem: float = 16.0
    req_gpu: int = 1
    status: str = "SUBMITTED" # SUBMITTED, QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
    progress: float = 0.0
    assigned_node: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    retries: int = 0

class TrainingOrchestrator:
    def __init__(self):
        self.balancer = WorkloadBalancer()
        self.scheduler = JobScheduler()
        self.jobs: Dict[str, JobState] = {}
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

        # Pre-seed simulated cluster compute nodes
        for i in range(1, 11):
            has_gpu = (i <= 6)
            self.balancer.register_node(ComputeNode(
                node_id=f"gpu-worker-node-{i:02d}",
                total_cpu=32.0,
                total_memory_gb=128.0,
                total_gpu=4 if has_gpu else 0,
            ))

    async def start(self):
        self._running = True
        self._worker_task = asyncio.create_task(self._scheduling_loop())
        logger.info("Training Orchestrator started scheduling background loop")

    async def stop(self):
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
        logger.info("Training Orchestrator stopped cleanly")

    async def submit_job(
        self,
        model_type: str,
        dataset_id: str,
        hyperparameters: Dict[str, Any],
        priority: int = 5,
        req_cpu: float = 4.0,
        req_mem: float = 16.0,
        req_gpu: int = 1,
    ) -> JobState:
        job_id = f"train-{uuid.uuid4().hex[:12]}"
        job = JobState(
            job_id=job_id,
            model_type=model_type,
            dataset_id=dataset_id,
            hyperparameters=hyperparameters,
            priority=priority,
            req_cpu=req_cpu,
            req_mem=req_mem,
            req_gpu=req_gpu,
            status="QUEUED"
        )
        self.jobs[job_id] = job

        queued = QueuedJob(
            priority=priority,
            job_id=job_id,
            model_type=model_type,
            req_cpu=req_cpu,
            req_mem=req_mem,
            req_gpu=req_gpu
        )
        await self.scheduler.enqueue(queued)
        return job

    async def cancel_job(self, job_id: str) -> bool:
        if job_id not in self.jobs:
            return False
        job = self.jobs[job_id]
        if job.status == "QUEUED":
            await self.scheduler.remove(job_id)
            job.status = "CANCELLED"
            return True
        elif job.status == "RUNNING":
            if job.assigned_node:
                self.balancer.release(job.assigned_node, job_id, job.req_cpu, job.req_mem, job.req_gpu)
            job.status = "CANCELLED"
            return True
        return False

    async def retry_job(self, job_id: str) -> bool:
        if job_id not in self.jobs:
            return False
        job = self.jobs[job_id]
        if job.status in ["FAILED", "CANCELLED"]:
            job.status = "QUEUED"
            job.retries += 1
            job.progress = 0.0
            queued = QueuedJob(
                priority=job.priority,
                job_id=job.job_id,
                model_type=job.model_type,
                req_cpu=job.req_cpu,
                req_mem=job.req_mem,
                req_gpu=job.req_gpu
            )
            await self.scheduler.enqueue(queued)
            return True
        return False

    async def _scheduling_loop(self):
        while self._running:
            try:
                job_req = await self.scheduler.pop_next()
                if not job_req:
                    await asyncio.sleep(0.5)
                    continue

                best_node = self.balancer.select_best_node(
                    job_req.req_cpu, job_req.req_mem, job_req.req_gpu
                )

                if best_node:
                    self.balancer.allocate(
                        best_node, job_req.job_id, job_req.req_cpu, job_req.req_mem, job_req.req_gpu
                    )
                    job = self.jobs[job_req.job_id]
                    job.status = "RUNNING"
                    job.assigned_node = best_node
                    job.started_at = time.time()
                    logger.info("Assigned job to node", job_id=job.job_id, node=best_node)

                    # Trigger simulated training progress in background
                    asyncio.create_task(self._simulate_execution(job))
                else:
                    # No node currently has resources; re-enqueue with slight delay
                    await self.scheduler.enqueue(job_req)
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in orchestrator scheduling loop", error=str(e))
                await asyncio.sleep(1.0)

    async def _simulate_execution(self, job: JobState):
        for step in range(1, 11):
            await asyncio.sleep(0.2)
            if job.status != "RUNNING":
                return
            job.progress = round(step * 0.1, 2)
            job.metrics["loss"] = round(1.0 / (step + 1), 4)
            job.metrics["accuracy"] = round(0.5 + (0.04 * step), 4)

        job.status = "COMPLETED"
        job.completed_at = time.time()
        if job.assigned_node:
            self.balancer.release(job.assigned_node, job.job_id, job.req_cpu, job.req_mem, job.req_gpu)
        logger.info("Job completed successfully", job_id=job.job_id)

orchestrator_instance = TrainingOrchestrator()
