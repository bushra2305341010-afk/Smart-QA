# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: SemVer.
Sections: Added, Changed, Fixed, Security, Removed, Deprecated.

## [Unreleased]

### Fixed
- CI `web`: pnpm 12 fails on unapproved build scripts in CI; esbuild's build is now approved in `apps/web/pnpm-workspace.yaml`.
- CI `secrets`: `.gitleaks.toml` keeps default rules and allowlists only the fake secret-shaped redaction-test fixtures.

### Added
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
