# Sector 01 · Connect and Ingest

**Features:** F01 repo, F02 documents, F03 issues/stories, N01 environments, N02 identity vault, N03 HAR (v1), N04 setup wizard.
**Owner:** Nadia (docs/code), Stuti (runner/env).

## Flow

```
User ─▶ Setup wizard ─▶ POST /sources ─▶ store original (MinIO, sha256)
     ─▶ q.understand: parse (PyMuPDF / python-docx / markdown-it / OpenAPI)
     ─▶ chunk with start/end offsets + page + line ─▶ embed ─▶ chunk table
Repo ─▶ read-only clone ─▶ tree-sitter facts (routes, forms, validators, endpoints)
Env  ─▶ environment row + runner binding ─▶ runner health check
Identities ─▶ vault (encrypted) — model only sees {{secret:name}}
```

## Code map

| Concern | Path |
|---|---|
| API | `apps/api/routers/sources.py`, `environments.py`, `identities.py` |
| Parsers | `packages/citations/parsers/{pdf,docx,md,openapi}.py` |
| Chunker | `packages/citations/chunker.py` |
| Embeddings | `packages/citations/embed.py` |
| Git import | `packages/analyzers/code/git_source.py` |
| Vault | `apps/api/vault.py` |
| UI | `apps/web/src/features/setup/` |

## Inputs / outputs (contract)

- In: file (≤ 50 MB, type by magic bytes) or repo URL + ref.
- Out: `source{status}`; `chunk{text,start_offset,end_offset,page,line}`. **Offsets are positions in the normalised text stored with the source**, which the quote verifier uses — never change normalisation without a re-ingest migration.

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Upload 400 "unsupported type" | `sources.py` validator | Add MIME/magic mapping |
| Page/line wrong in UI | `parsers/pdf.py` | Line counting per page; hyphenation joins |
| DOCX tables missing | `parsers/docx.py` | Iterate tables, not only paragraphs |
| Quote check fails right after ingest | `chunker.py` normalisation | Whitespace/Unicode NFC mismatch between stored text and offsets |
| Repo clone hangs | `git_source.py` | Timeout, depth=1, auth token |
| Runner "unreachable env" | Env `allowed_hosts`, runner logs | Host missing, DNS inside container |
| Secret visible in log | `vault.py`, logging filters | Redaction filter; never `repr()` secrets |

## Change safety

- [ ] `make test-ingest`
- [ ] If parser/chunker/normalisation changed → `make test-citations test-designer test-judge` + re-ingest golden projects + `evals-small`
- [ ] If env/identity schema changed → `make test-runner`
- [ ] Update `07-database.md` if columns changed
