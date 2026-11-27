"""Object storage for originals, normalised texts and evidence (ADR-007, ADR-010).

Keys are content addresses (`sources/<sha256>`), so the same bytes are stored once and a stored
object can be checked against its name. Only the S3 API is used (SeaweedFS locally, company S3
in production).
"""

from __future__ import annotations

import hashlib
from typing import Any, Protocol


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_key(sha256: str) -> str:
    return f"sources/{sha256}"


def evidence_key(sha256: str) -> str:
    """Runner evidence (screenshot, trace, console log) by content address (ADR-007)."""
    return f"evidence/{sha256[:2]}/{sha256}"


def text_key(sha256: str) -> str:
    """Normalised text of a source; chunk offsets and quote checks index into it."""
    return f"texts/{sha256}.txt"


class IntegrityError(Exception):
    """Stored bytes do not match their content address."""


class S3ObjectStore:
    def __init__(self, client: Any, bucket: str) -> None:
        self._s3 = client
        self.bucket = bucket
        self._ready = False

    @classmethod
    def from_settings(
        cls, endpoint: str, bucket: str, access_key: str, secret_key: str
    ) -> S3ObjectStore:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
            config=Config(
                s3={"addressing_style": "path"},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )
        return cls(client, bucket)

    def ensure_bucket(self) -> None:
        """Create the bucket on first write (no network call at app start-up)."""
        if self._ready:
            return
        names = {b["Name"] for b in self._s3.list_buckets().get("Buckets", [])}
        if self.bucket not in names:
            self._s3.create_bucket(Bucket=self.bucket)
        self._ready = True

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.ensure_bucket()
        self._s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        data: bytes = self._s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        if key.startswith("sources/") and sha256_hex(data) != key.removeprefix("sources/"):
            raise IntegrityError(f"{key} does not match its hash")
        return data


class MemoryObjectStore:
    """Tests and the laptop dev loop without S3."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    def get(self, key: str) -> bytes:
        return self.objects[key][0]
