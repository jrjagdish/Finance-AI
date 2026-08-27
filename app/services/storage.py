import os
import uuid

from app.core.config import settings


class LocalFileStorage:
    """Local-disk stand-in for the S3/MinIO raw file store.

    Same interface (`save`/`path_for`) an S3/MinIO-backed implementation
    would expose, so swapping the backend later doesn't touch callers.
    """

    def __init__(self, root: str | None = None):
        self.root = root or settings.storage_dir
        os.makedirs(self.root, exist_ok=True)

    def save(self, batch_id: uuid.UUID, filename: str, content: bytes) -> str:
        batch_dir = os.path.join(self.root, str(batch_id))
        os.makedirs(batch_dir, exist_ok=True)
        file_key = f"{batch_id}/{filename}"
        with open(os.path.join(batch_dir, filename), "wb") as f:
            f.write(content)
        return file_key

    def path_for(self, file_key: str) -> str:
        return os.path.join(self.root, file_key)


storage = LocalFileStorage()
