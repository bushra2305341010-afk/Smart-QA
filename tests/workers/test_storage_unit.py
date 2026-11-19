"""Object store adapters (no network)."""

import io

import pytest

from apps.api.storage import (
    IntegrityError,
    MemoryObjectStore,
    S3ObjectStore,
    sha256_hex,
    source_key,
    text_key,
)


class FakeS3:
    def __init__(self, buckets: list[str]) -> None:
        self.buckets = buckets
        self.objects: dict[str, bytes] = {}
        self.list_calls = 0

    def list_buckets(self) -> dict:
        self.list_calls += 1
        return {"Buckets": [{"Name": b} for b in self.buckets]}

    def create_bucket(self, Bucket: str) -> None:
        self.buckets.append(Bucket)

    def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:
        self.objects[Key] = Body

    def get_object(self, Bucket: str, Key: str) -> dict:
        return {"Body": io.BytesIO(self.objects[Key])}


def test_s3_store_creates_bucket_once_and_checks_hashes() -> None:
    fake = FakeS3([])
    store = S3ObjectStore(fake, "evidence")
    data = b"hello"
    store.put(source_key(sha256_hex(data)), data, "text/plain")
    store.put(text_key("abc"), b"t", "text/plain")
    assert fake.buckets == ["evidence"] and fake.list_calls == 1
    assert store.get(source_key(sha256_hex(data))) == data
    assert store.get(text_key("abc")) == b"t"
    fake.objects[source_key(sha256_hex(data))] = b"tampered"
    with pytest.raises(IntegrityError):
        store.get(source_key(sha256_hex(data)))


def test_existing_bucket_is_not_recreated() -> None:
    fake = FakeS3(["evidence"])
    S3ObjectStore(fake, "evidence").put("k", b"v", "text/plain")
    assert fake.buckets == ["evidence"]


def test_from_settings_builds_client_without_network() -> None:
    store = S3ObjectStore.from_settings("http://localhost:1", "b", "k", "s")
    assert store.bucket == "b"


def test_memory_store() -> None:
    store = MemoryObjectStore()
    store.put("k", b"v", "text/plain")
    assert store.get("k") == b"v"
    with pytest.raises(KeyError):
        store.get("missing")
