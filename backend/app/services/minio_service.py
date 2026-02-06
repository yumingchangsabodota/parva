"""MinIO file storage service."""

from __future__ import annotations

import io
import uuid
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings
from app.models.schemas import FileRef


class MinIOService:
    def __init__(self) -> None:
        s = get_settings()
        self.client = Minio(
            s.minio_endpoint,
            access_key=s.minio_access_key,
            secret_key=s.minio_secret_key,
            secure=s.minio_secure,
        )
        self.bucket = s.minio_bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    async def upload_file(
        self,
        user_id: str,
        filename: str,
        data: BinaryIO,
        content_type: str,
        size: int,
    ) -> FileRef:
        key = f"{user_id}/{uuid.uuid4().hex}/{filename}"
        self.client.put_object(
            self.bucket,
            key,
            data,
            length=size,
            content_type=content_type,
        )
        return FileRef(
            key=key,
            filename=filename,
            content_type=content_type,
            size=size,
        )

    async def download_file(self, key: str) -> bytes:
        resp = self.client.get_object(self.bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    async def get_presigned_url(self, key: str, expires_hours: int = 1) -> str:
        from datetime import timedelta

        return self.client.presigned_get_object(
            self.bucket,
            key,
            expires=timedelta(hours=expires_hours),
        )

    async def delete_file(self, key: str) -> None:
        self.client.remove_object(self.bucket, key)

    async def copy_to_workspace(self, key: str, dest_path: str) -> str:
        """Download a file from MinIO and return its bytes for workspace injection."""
        data = await self.download_file(key)
        return data
