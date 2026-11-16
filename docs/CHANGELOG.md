# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: SemVer.
Sections: Added, Changed, Fixed, Security, Removed, Deprecated.

## [Unreleased]

### Fixed
- Local dev S3: the `minio/minio` image is no longer published on Docker Hub or quay.io; Compose now runs SeaweedFS 4.00 (`s3` service, port 8333, keys in `deploy/seaweedfs/s3.json`). Verified with boto3: bucket create, put, head, get (hash match), list, presigned GET, wrong-key rejection (ADR-010).
- Removed the Starlette TestClient warning filter (T-007): the official SDK brings `httpx2`, so tests run with warnings as errors and no exceptions.
- CI `web`: pnpm 12 fails on unapproved build scripts in CI; esbuild's build is now approved in `apps/web/pnpm-workspace.yaml`.
- CI `secrets`: `.gitleaks.toml` keeps default rules and allowlists only the fake secret-shaped redaction-test fixtures.

### Added
- T-602 local model: `LocalProvider` for OpenAI-compatible local servers (Ollama, llama.cpp, vLLM, LM Studio) and `build_provider()` that enforces the `local-only` policy in code (no Claude provider, internal hosts only). New settings `LOCAL_MODEL_URL`, `LOCAL_MODEL_NAME`.
- M06 model gateway: `packages/model_gateway` with the Claude adapter (official `anthropic` SDK 2.x; structured JSON output, explicit effort, prompt caching of stable context, server-side refusal fallbacks), redaction of PII/secrets, untrusted-data wrapping, replay cache, cost accounting, budget pre-check, schema validation with up to 2 retries. 100% branch coverage.
- M04 planning: `packages/contracts/plan.py` and `packages/planning` (`technique_rows`, `risk_score`, `priority_for`, `suggest_segment`, `estimate_design_cost`). Counts are deterministic code with a reason per technique; risk multiplier 0.7-1.5; Must/Should/Could; cost estimate with budget check. 100% branch coverage.
- M02 citations: `packages/contracts/citation.py` (`Citation`, `Chunk`, `Location`), `packages/citations` with `normalize_text`, `chunk_pages` (offsets, page, line) and `verify_quote` / `verify_citation` (exact match after normalisation, offset correction, short-quote rejection). 100% branch coverage.
- M01 foundation: repo skeleton (apps/, packages/, evals/ with READMEs), uv/ruff/mypy/pytest config, FastAPI app with `/api/v1/healthz` and `/api/v1/readyz`, Docker Compose (Postgres+pgvector, Redis, MinIO, API), CI (python, web, gitleaks), pre-commit, Makefile, `.env.example`.
- Web scaffold: React 18 + TypeScript + Vite, design tokens, `VerdictBadge` with tests.
- `CONTRIBUTING.md` and `stuti.md` contributor guide (fork, setup, workflow, module plan, testing and documentation plan).
- Engineering documentation set (`docs/`), sector workflows, bug-triage map.
- Frontend design system "Verified Indigo" (tokens in `05-frontend-ui-design.md`).

## [0.0.0] - 2026-10-07
### Added
- Project proposal, gap analysis, market comparison workbook (research phase).
