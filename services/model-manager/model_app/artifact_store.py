import hashlib
import os
from typing import Optional, Dict
import structlog

logger = structlog.get_logger(__name__)

class ArtifactStore:
    def __init__(self, root_dir: str = "/tmp/hams_model_artifacts"):
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)
        self._in_memory_blobs: Dict[str, bytes] = {}

    def store_artifact(self, filename: str, content: bytes) -> str:
        sha = hashlib.sha256(content).hexdigest()
        self._in_memory_blobs[sha] = content

        file_path = os.path.join(self.root_dir, f"{sha}_{filename}")
        try:
            with open(file_path, "wb") as f:
                f.write(content)
        except Exception as e:
            logger.warn("Disk write failed for artifact, keeping in memory", error=str(e))

        logger.info("Stored model artifact", sha256=sha, size_bytes=len(content))
        return sha

    def get_artifact(self, sha256: str) -> Optional[bytes]:
        if sha256 in self._in_memory_blobs:
            return self._in_memory_blobs[sha256]

        # Scan root_dir
        for f in os.listdir(self.root_dir):
            if f.startswith(sha256):
                with open(os.path.join(self.root_dir, f), "rb") as fp:
                    return fp.read()
        return None

    def generate_signed_download_url(self, sha256: str, expiry_seconds: int = 3600) -> str:
        return f"https://azure-blob.hams.ai/models/{sha256}?sig=mock_secure_token&exp={expiry_seconds}"
