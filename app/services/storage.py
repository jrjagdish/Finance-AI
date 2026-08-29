import logging
import uuid

import cloudinary
import cloudinary.uploader
import cloudinary.utils

from app.core.config import settings

logger = logging.getLogger(__name__)


class CloudinaryFileStorage:
    """Cloud-based archive for raw uploaded files, backed by Cloudinary (resource_type="raw").

    Same interface (`save`/`path_for`) the previous local-disk implementation
    exposed, so callers didn't need to change. Serverless hosts like Vercel
    have a read-only filesystem, so this can no longer write to disk.
    """

    def __init__(self):
        self.configured = bool(
            settings.cloudinary_cloud_name
            and settings.cloudinary_api_key
            and settings.cloudinary_api_secret
        )
        if self.configured:
            cloudinary.config(
                cloud_name=settings.cloudinary_cloud_name,
                api_key=settings.cloudinary_api_key,
                api_secret=settings.cloudinary_api_secret,
                secure=True,
            )
        else:
            logger.warning("Cloudinary credentials not set; uploaded files will not be archived.")

    def save(self, batch_id: uuid.UUID, filename: str, content: bytes) -> str:
        file_key = f"{batch_id}/{filename}"
        if not self.configured:
            return file_key
        try:
            cloudinary.uploader.upload(
                content,
                resource_type="raw",
                public_id=file_key,
                overwrite=True,
            )
        except Exception:
            # Archiving is best-effort — parsed rows are already committed to the
            # DB by the caller, so a failed upload shouldn't fail the request.
            logger.exception("Failed to archive %s to Cloudinary", file_key)
        return file_key

    def path_for(self, file_key: str) -> str:
        if not self.configured:
            return file_key
        url, _ = cloudinary.utils.cloudinary_url(file_key, resource_type="raw")
        return url


storage = CloudinaryFileStorage()
