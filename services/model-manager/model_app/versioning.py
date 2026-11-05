from dataclasses import dataclass, field
import time
from typing import Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)

@dataclass
class ModelVersion:
    version_id: str # e.g. v1.0.0, v1.1.0
    artifact_sha: str
    stage: str = "staging" # draft, staging, production, archived
    metrics: Dict[str, float] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    promoted_at: Optional[float] = None
    changelog: str = ""

class ModelVersioning:
    def __init__(self):
        self._versions: Dict[str, List[ModelVersion]] = {}

    def create_version(
        self,
        model_id: str,
        version_id: str,
        artifact_sha: str,
        metrics: Optional[Dict[str, float]] = None,
        changelog: str = ""
    ) -> ModelVersion:
        if model_id not in self._versions:
            self._versions[model_id] = []

        # Check uniqueness
        for v in self._versions[model_id]:
            if v.version_id == version_id:
                raise ValueError(f"Version {version_id} already exists for model {model_id}")

        ver = ModelVersion(
            version_id=version_id,
            artifact_sha=artifact_sha,
            stage="staging",
            metrics=metrics or {},
            changelog=changelog
        )
        self._versions[model_id].append(ver)
        logger.info("Created model version", model_id=model_id, version=version_id)
        return ver

    def promote_version(self, model_id: str, version_id: str, target_stage: str) -> Optional[ModelVersion]:
        if model_id not in self._versions:
            return None

        target_ver = None
        for v in self._versions[model_id]:
            if v.version_id == version_id:
                target_ver = v
            elif target_stage == "production" and v.stage == "production":
                # Demote existing production to archived
                v.stage = "archived"

        if target_ver:
            target_ver.stage = target_stage
            target_ver.promoted_at = time.time()
            logger.info("Promoted model version", model_id=model_id, version=version_id, stage=target_stage)
            return target_ver
        return None

    def list_versions(self, model_id: str) -> List[ModelVersion]:
        return list(self._versions.get(model_id, []))
