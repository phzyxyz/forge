"""Multi-cloud object storage backends (S3-compatible, Azure, GCS)."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urljoin

from phzyx.orm.files import sanitize_upload_key


@dataclass
class S3CompatibleStorage:
    """S3 / MinIO / R2 via boto3 (optional dependency).

    For tests without boto3, pass a custom ``client`` with put_object/get_object/...
    """

    bucket: str
    prefix: str = ""
    endpoint_url: str | None = None
    region_name: str | None = None
    public_base_url: str | None = None
    client: Any | None = None
    _mem: dict[str, bytes] = field(default_factory=dict)  # fallback if no client

    def _client(self) -> Any:
        if self.client is not None:
            return self.client
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise ImportError("S3 storage requires boto3: uv add boto3") from exc
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
        )

    def _key(self, key: str) -> str:
        safe = sanitize_upload_key(key)
        return f"{self.prefix.rstrip('/')}/{safe}" if self.prefix else safe

    def save(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        k = self._key(key)
        client = self._client() if self.client is not None or _has_boto3() else None
        if client is None:
            self._mem[k] = data
        else:
            extra: dict[str, Any] = {}
            if content_type:
                extra["ContentType"] = content_type
            client.put_object(Bucket=self.bucket, Key=k, Body=data, **extra)
        return sanitize_upload_key(key)

    def open(self, key: str) -> bytes:
        k = self._key(key)
        if self.client is None and not _has_boto3():
            return self._mem[k]
        client = self._client()
        obj = client.get_object(Bucket=self.bucket, Key=k)
        body = obj["Body"]
        return body.read() if hasattr(body, "read") else bytes(body)

    def delete(self, key: str) -> None:
        k = self._key(key)
        if self.client is None and not _has_boto3():
            self._mem.pop(k, None)
            return
        self._client().delete_object(Bucket=self.bucket, Key=k)

    def exists(self, key: str) -> bool:
        k = self._key(key)
        if self.client is None and not _has_boto3():
            return k in self._mem
        try:
            self._client().head_object(Bucket=self.bucket, Key=k)
            return True
        except Exception:
            return False

    def url(self, key: str) -> str | None:
        safe = sanitize_upload_key(key)
        if self.public_base_url:
            return urljoin(self.public_base_url.rstrip("/") + "/", safe)
        return None

    def presign(self, key: str, *, expires_in: int = 3600, method: str = "get_object") -> str:
        """Generate a signed URL (requires real boto3 client)."""
        k = self._key(key)
        client = self._client()
        return client.generate_presigned_url(
            ClientMethod=method,
            Params={"Bucket": self.bucket, "Key": k},
            ExpiresIn=expires_in,
        )

    def presign_put(
        self,
        key: str,
        *,
        expires_in: int = 3600,
        content_type: str | None = None,
    ) -> str:
        params: dict[str, Any] = {"Bucket": self.bucket, "Key": self._key(key)}
        if content_type:
            params["ContentType"] = content_type
        return self._client().generate_presigned_url(
            ClientMethod="put_object",
            Params=params,
            ExpiresIn=expires_in,
        )

    def presign_get(self, key: str, *, expires_in: int = 3600) -> str:
        return self.presign(key, expires_in=expires_in, method="get_object")


@dataclass
class AzureBlobStorage:
    """Azure Blob backend (optional azure-storage-blob)."""

    container: str
    connection_string: str | None = None
    account_url: str | None = None
    credential: Any | None = None
    public_base_url: str | None = None
    _mem: dict[str, bytes] = field(default_factory=dict)
    client: Any | None = None

    def _blob(self, key: str) -> Any:
        if self.client is not None:
            return self.client
        try:
            from azure.storage.blob import BlobServiceClient  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise ImportError("Azure storage requires azure-storage-blob") from exc
        if self.connection_string:
            svc = BlobServiceClient.from_connection_string(self.connection_string)
        else:
            svc = BlobServiceClient(account_url=self.account_url, credential=self.credential)
        return svc.get_blob_client(container=self.container, blob=sanitize_upload_key(key))

    def save(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        k = sanitize_upload_key(key)
        try:
            blob = self._blob(k)
            blob.upload_blob(data, overwrite=True, content_type=content_type)
        except ImportError:
            self._mem[k] = data
        return k

    def open(self, key: str) -> bytes:
        k = sanitize_upload_key(key)
        if k in self._mem:
            return self._mem[k]
        return self._blob(k).download_blob().readall()

    def delete(self, key: str) -> None:
        k = sanitize_upload_key(key)
        self._mem.pop(k, None)
        with suppress(Exception):
            self._blob(k).delete_blob()

    def exists(self, key: str) -> bool:
        k = sanitize_upload_key(key)
        if k in self._mem:
            return True
        try:
            return bool(self._blob(k).exists())
        except Exception:
            return False

    def url(self, key: str) -> str | None:
        if self.public_base_url:
            return urljoin(self.public_base_url.rstrip("/") + "/", sanitize_upload_key(key))
        return None

    def presign_put(
        self,
        key: str,
        *,
        expires_in: int = 3600,
        content_type: str | None = None,
    ) -> str:
        """SAS URL for upload (requires azure-storage-blob)."""
        k = sanitize_upload_key(key)
        if k in self._mem:
            return f"memory://{self.container}/{k}?put=1&exp={expires_in}"
        try:
            from azure.storage.blob import BlobSasPermissions, generate_blob_sas
        except ImportError as exc:  # pragma: no cover
            raise ImportError("Azure presign requires azure-storage-blob") from exc
        blob = self._blob(k)
        # Best-effort: use account key from connection string if available
        account_name = getattr(blob, "account_name", None) or "account"
        account_key = self.credential if isinstance(self.credential, str) else None
        if account_key is None and self.connection_string:
            for part in self.connection_string.split(";"):
                if part.startswith("AccountKey="):
                    account_key = part.split("=", 1)[1]
                if part.startswith("AccountName="):
                    account_name = part.split("=", 1)[1]
        if not account_key:
            raise RuntimeError("Azure presign needs AccountKey credential")
        sas = generate_blob_sas(
            account_name=account_name,
            container_name=self.container,
            blob_name=k,
            account_key=account_key,
            permission=BlobSasPermissions(write=True, create=True),
            expiry=datetime.now(UTC) + timedelta(seconds=expires_in),
            content_type=content_type,
        )
        base = (
            blob.url
            if hasattr(blob, "url")
            else f"https://{account_name}.blob.core.windows.net/{self.container}/{k}"
        )
        return f"{base}?{sas}"

    def presign_get(self, key: str, *, expires_in: int = 3600) -> str:
        k = sanitize_upload_key(key)
        if k in self._mem:
            return f"memory://{self.container}/{k}?get=1&exp={expires_in}"
        try:
            from azure.storage.blob import BlobSasPermissions, generate_blob_sas
        except ImportError as exc:  # pragma: no cover
            raise ImportError("Azure presign requires azure-storage-blob") from exc
        blob = self._blob(k)
        account_name = getattr(blob, "account_name", None) or "account"
        account_key = self.credential if isinstance(self.credential, str) else None
        if account_key is None and self.connection_string:
            for part in self.connection_string.split(";"):
                if part.startswith("AccountKey="):
                    account_key = part.split("=", 1)[1]
                if part.startswith("AccountName="):
                    account_name = part.split("=", 1)[1]
        if not account_key:
            raise RuntimeError("Azure presign needs AccountKey credential")
        sas = generate_blob_sas(
            account_name=account_name,
            container_name=self.container,
            blob_name=k,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(UTC) + timedelta(seconds=expires_in),
        )
        base = (
            blob.url
            if hasattr(blob, "url")
            else f"https://{account_name}.blob.core.windows.net/{self.container}/{k}"
        )
        return f"{base}?{sas}"


@dataclass
class GCSStorage:
    """Google Cloud Storage backend (optional google-cloud-storage)."""

    bucket_name: str
    public_base_url: str | None = None
    client: Any | None = None
    _mem: dict[str, bytes] = field(default_factory=dict)

    def _bucket(self) -> Any:
        if self.client is not None:
            return self.client.bucket(self.bucket_name)
        try:
            from google.cloud import storage as gcs  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise ImportError("GCS storage requires google-cloud-storage") from exc
        return gcs.Client().bucket(self.bucket_name)

    def save(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        k = sanitize_upload_key(key)
        try:
            blob = self._bucket().blob(k)
            blob.upload_from_string(data, content_type=content_type)
        except ImportError:
            self._mem[k] = data
        return k

    def open(self, key: str) -> bytes:
        k = sanitize_upload_key(key)
        if k in self._mem:
            return self._mem[k]
        return self._bucket().blob(k).download_as_bytes()

    def delete(self, key: str) -> None:
        k = sanitize_upload_key(key)
        self._mem.pop(k, None)
        with suppress(Exception):
            self._bucket().blob(k).delete()

    def exists(self, key: str) -> bool:
        k = sanitize_upload_key(key)
        if k in self._mem:
            return True
        try:
            return bool(self._bucket().blob(k).exists())
        except Exception:
            return False

    def url(self, key: str) -> str | None:
        if self.public_base_url:
            return urljoin(self.public_base_url.rstrip("/") + "/", sanitize_upload_key(key))
        return None

    def presign_put(
        self,
        key: str,
        *,
        expires_in: int = 3600,
        content_type: str | None = None,
    ) -> str:
        k = sanitize_upload_key(key)
        if k in self._mem:
            return f"memory://{self.bucket_name}/{k}?put=1&exp={expires_in}"
        blob = self._bucket().blob(k)
        return blob.generate_signed_url(
            version="v4",
            expiration=expires_in,
            method="PUT",
            content_type=content_type,
        )

    def presign_get(self, key: str, *, expires_in: int = 3600) -> str:
        k = sanitize_upload_key(key)
        if k in self._mem:
            return f"memory://{self.bucket_name}/{k}?get=1&exp={expires_in}"
        blob = self._bucket().blob(k)
        return blob.generate_signed_url(
            version="v4",
            expiration=expires_in,
            method="GET",
        )


def _has_boto3() -> bool:
    try:
        import boto3  # type: ignore[import-not-found]  # noqa: F401

        return True
    except ImportError:
        return False
