# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: SemVer.
Sections: Added, Changed, Fixed, Security, Removed, Deprecated.

## [Unreleased]

### Added
- M02 citations: `packages/contracts/citation.py` (`Citation`, `Chunk`, `Location`), `packages/citations` with `normalize_text`, `chunk_pages` (offsets, page, line) and `verify_quote` / `verify_citation` (exact match after normalisation, offset correction, short-quote rejection). 100% branch coverage.
- M01 foundation: repo skeleton (apps/, packages/, evals/ with READMEs), uv/ruff/mypy/pytest config, FastAPI app with `/api/v1/healthz` and `/api/v1/readyz`, Docker Compose (Postgres+pgvector, Redis, MinIO, API), CI (python, web, gitleaks), pre-commit, Makefile, `.env.example`.
- Web scaffold: React 18 + TypeScript + Vite, design tokens, `VerdictBadge` with tests.
- `CONTRIBUTING.md` and `stuti.md` contributor guide (fork, setup, workflow, module plan, testing and documentation plan).
- Engineering documentation set (`docs/`), sector workflows, bug-triage map.
- Frontend design system "Verified Indigo" (tokens in `05-frontend-ui-design.md`).

## [0.0.0] - 2026-10-07
### Added
- Project proposal, gap analysis, market comparison workbook (research phase).
