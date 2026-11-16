# ADR-010: SeaweedFS as the local S3-compatible evidence store

**Status:** Accepted · **Date:** 2026-11-17

## Context
The design calls for S3-compatible object storage for evidence (screenshots, traces, HAR, documents). Local development used the `minio/minio` image, which is no longer published on Docker Hub or quay.io, so `docker compose up` failed. Production deployments use the company's own S3-compatible storage (docs/21 B2), so the local choice only affects laptops and CI.

## Decision
Run SeaweedFS (`chrislusf/seaweedfs:4.00`, Apache-2.0) as the `s3` Compose service on port 8333, with access keys in `deploy/seaweedfs/s3.json`. The application talks to storage only through the S3 API with boto3 (path-style addressing, `request_checksum_calculation="when_required"`), never through vendor-specific APIs.

## Consequences
- `docker compose up` works again; verified put/head/get/list/presigned GET and wrong-key rejection with boto3.
- AWS CLI v2 uploads (streaming checksums) are not read back correctly by SeaweedFS 4.00; use boto3 for manual checks.
- Because only the S3 API is used, any other S3-compatible store (company S3, Garage, RustFS) works by changing `S3_ENDPOINT` and keys.

## Alternatives considered
- MinIO from another registry: no maintained public image found.
- Garage: needs a layout-initialisation step before first use; more setup for students.
- RustFS: MinIO-compatible but much younger project.
- LocalStack: heavier, emulates many AWS services we don't need.
