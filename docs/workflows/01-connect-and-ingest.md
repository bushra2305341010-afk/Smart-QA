# Sector 01 · Connect and Ingest

**Features:** F01 repo, F02 documents, F03 issues/stories, N01 environments, N02 identity vault, N03 HAR (v1), N04 setup wizard.
**Owner:** Nadia (docs/code), Stuti (runner/env).

## Flow

```
User ─▶ Setup wizard ─▶ POST /sources ─▶ store original (S3, sha256)
     ─▶ q.understand: parse (PyMuPDF / python-docx / markdown-it / OpenAPI)
     ─▶ chunk with start/end offsets + page + line ─▶ embed ─▶ chunk table
Repo ─▶ read-only clone ─▶ tree-sitter facts (routes, forms, validators, endpoints)
Env  ─▶ environment row + runner binding ─▶ runner health check
Identities ─▶ vault (encrypted) — model only sees {{secret:name}}
```

## Code map

| Concern | Path |
|---|---|
| API | `apps/api/routers/projects.py` (`POST /projects/{id}/sources/upload`, sources, environments, identities) |
| Type detection (magic bytes) + parser registry | `packages/citations/parsers/__init__.py` |
| Parsers | `packages/citations/parsers/{pdf,docx,markdown,openapi}.py` (PDF via pypdf, BSD licence) |
| Object storage (content-addressed `sources/<sha256>`, `texts/<sha256>.txt`) | `apps/api/storage.py` |
| Ingest worker (`job.ingest`) | `apps/workers/ingest.py`, consumer `apps/workers/consumer.py` |
| Chunker | `packages/citations/chunker.py` |
| Embeddings | `packages/citations/embed.py` (not yet; `chunk.embedding` stays NULL until then) |
| Git import (read-only, shallow, SSRF-guarded) | `apps/workers/git_source.py` (clone + safe file walk), URL rules `packages/analyzers/code/repo_url.py`, code facts `packages/analyzers/code/facts.py` |
| Vault | `apps/api/vault.py` |
| UI | `apps/web/src/features/setup/` |

## Inputs / outputs (contract)

- In: file (≤ 50 MB, type by magic bytes) or repo URL + ref.
- Out: `source{status, filename, size, text_key, error}`; `chunk{text,start_offset,end_offset,page,line}`. The normalised full text is stored at `source.text_key`; same bytes uploaded twice return the existing source (sha256). A source that cannot be parsed is `failed` with `error`; the stage completes if at least one source is `ready`. **Offsets are positions in the normalised text stored with the source**, which the quote verifier uses — never change normalisation without a re-ingest migration.

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Upload 415 `UNSUPPORTED_TYPE` | `parsers/__init__.py:detect_kind` | Add magic-byte mapping + parser |
| Source stuck in `parsing` | Worker crashed mid-file | Next `job.ingest` (retry/recovery) picks up `parsing` sources again |
| `failed` "No text found" | Scanned PDF | Needs OCR (not in MVP) |
| Page/line wrong in UI | `parsers/pdf.py` | Line counting per page; hyphenation joins |
| DOCX tables missing | `parsers/docx.py` | Iterate tables, not only paragraphs |
| Quote check fails right after ingest | `chunker.py` normalisation | Whitespace/Unicode NFC mismatch between stored text and offsets |
| Repo clone hangs | `git_source.py` | 120 s timeout, depth 1, single branch; token from `GIT_READ_TOKEN` |
| Repo source `failed` "Only https …" | `repo_url.py` | Only https; no credentials in the URL; loopback / link-local hosts are refused |
| Few code facts | `facts.py` patterns | Add the framework's route/form pattern + a test (tree-sitter later) |
| Runner "unreachable env" | Env `allowed_hosts`, runner logs | Host missing, DNS inside container |
| Secret visible in log | `vault.py`, logging filters | Redaction filter; never `repr()` secrets |

## Change safety

- [ ] `tests/citations/test_parsers.py`, `tests/workers/` (ingest, consumer, storage)
- [ ] If parser/chunker/normalisation changed → `make test-citations test-designer test-judge` + re-ingest golden projects + `evals-small`
- [ ] If env/identity schema changed → `make test-runner`
- [ ] Update `07-database.md` if columns changed
