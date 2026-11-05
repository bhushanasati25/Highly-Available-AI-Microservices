import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import structlog

try:
    from .versioning import ModelVersioning, ModelVersion
    from .artifact_store import ArtifactStore
except ImportError:
    from versioning import ModelVersioning, ModelVersion
    from artifact_store import ArtifactStore

logger = structlog.get_logger(__name__)

@dataclass
class ModelRecord:
    id: str
    name: str
    framework: str
    description: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    lineage_dataset_id: Optional[str] = None
    lineage_training_job_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)

class ModelRegistry:
    def __init__(self):
        self.versioning = ModelVersioning()
        self.artifact_store = ArtifactStore()
        self._models: Dict[str, ModelRecord] = {}

    def register_model(
        self,
        name: str,
        framework: str,
        description: str = "",
        tags: Optional[Dict[str, str]] = None,
        dataset_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> ModelRecord:
        model_id = f"mod-{uuid.uuid4().hex[:10]}"
        record = ModelRecord(
            id=model_id,
            name=name,
            framework=framework,
            description=description,
            tags=tags or {},
            lineage_dataset_id=dataset_id,
            lineage_training_job_id=job_id,
        )
        self._models[model_id] = record

        # Seed initial v1.0.0 artifact
        dummy_weights = f"MockWeights_{name}_{framework}".encode("utf-8")
        sha = self.artifact_store.store_artifact(f"{name}_weights.bin", dummy_weights)
        self.versioning.create_version(
            model_id=model_id,
            version_id="v1.0.0",
            artifact_sha=sha,
            metrics={"val_loss": 0.25, "val_acc": 0.92},
            changelog="Initial baseline release"
        )

        logger.info("Registered new model in registry", model_id=model_id, name=name)
        return record

    def get_model(self, model_id: str) -> Optional[ModelRecord]:
        return self._models.get(model_id)

    def list_models(self) -> List[ModelRecord]:
        return list(self._models.values())

registry_instance = ModelRegistry()
