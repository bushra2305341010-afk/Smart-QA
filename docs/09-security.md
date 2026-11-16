# 09 · Security

## 1. Goals

1. User code, documents and data stay where the user decides.
2. The testing agent can never harm the system under test (SUT) or anything else.
3. Nothing the SUT shows can take control of our agent.
4. Every important action is traceable to a person or a rule.
5. Our own product passes the quality bar we sell.

## 2. Assets and trust boundaries

| Asset | Lives in | Main threat |
|---|---|---|
| Source code | User repo (read-only clone) | Leak to model provider / attacker |
| Product documents | Evidence store + DB | Leak, tampering |
| Test identities, API keys | Secret vault | Theft, exposure to model |
| Evidence (screens, HAR, logs) | Evidence store | Personal data, tampering |
| SUT | User network | Destructive actions, data pollution |
| Model provider key | Control-plane secret store | Theft, cost abuse |
| Audit ledger | DB | Tampering |

Boundaries: browser→API, API→runner, runner→SUT, gateway→model provider, orchestrator→trackers. **SUT page content is always untrusted.**

## 3. STRIDE threat model

| Threat | Example | Controls |
|---|---|---|
| Spoofing | Fake runner connects | Registration token + mTLS cert per runner, rotation |
| Tampering | Evidence/verdict edited later | SHA-256 per file, hash-chained ledger, write-once bucket |
| Repudiation | "I never approved that" | Gate decisions signed with user + time in ledger |
| Information disclosure | Code/PII sent to model | Local model option, redaction, data-sharing summary, per-project model policy |
| Denial of service | Runaway crawl / tokens | Step budgets, budget caps, rate limits, queue quotas |
| Elevation of privilege | Tester approves own plan | RBAC, gate permissions, server-side checks |

## 4. Prompt-injection defence (top AI risk, OWASP GenAI 2026 #1)

1. **Data, not instructions** — page/doc/log text wrapped and labelled untrusted.
2. **Fixed tool list** — no shell, file or raw network tools for Explorer/Healer.
3. **Policy engine outside the model** — every action checked by code against safe-action policy + domain allow-list.
4. **Plan lock** — execution runs compiled code, not live model decisions.
5. **Secrets never in context** — placeholders filled by the runner; output scanned for secret patterns.
6. **Output handling** — JSON parsed + schema-validated, never executed; generated code linted + import allow-list, runs only in sandbox.
7. **Red-team suite in CI** — hostile pages (hidden text, alt-text injection, fake dialogs). Any off-plan action fails the build.

## 5. Runner sandbox

- Fresh container + browser profile per test; nothing persists except approved evidence.
- Non-root, read-only root FS, dropped capabilities, seccomp, CPU/mem/time limits.
- Egress only to environment's allowed hosts + control plane.
- Never accepts inbound connections; outbound WSS over mTLS.
- Production URLs blocked unless an Owner marks the env production-safe; destructive actions blocked even then.

## 6. Safe-action policy (default)

| Category | Default | Detection |
|---|---|---|
| Delete / remove / close account | Block | Button text, aria-label, HTTP DELETE, route patterns |
| Pay / checkout submit with real card | Block unless `safe.payments=test` | Payment forms, known PSP hosts |
| Transfer money | Block | Keywords + routes |
| Send email / SMS / invite | Block unless env has mail sink | Keywords, endpoints |
| Off-domain navigation | Block | URL host ∉ allowed_hosts |
| File upload | Allow only fixtures from `evals/fixtures` | — |

Policy lives in `packages/policy`, 100% branch coverage required.

## 7. Application security

See [10-authentication-and-security.md](10-authentication-and-security.md) for auth. Also:

| Area | Control |
|---|---|
| Input | Pydantic validation, upload size limits, file-type by magic bytes, parsing in separate worker process |
| Web | Strict CSP, React output encoding, no `dangerouslySetInnerHTML` for model output, HSTS, X-Content-Type-Options, frame-ancestors none |
| Encryption | TLS 1.3 in transit; DB and object store encrypted at rest |
| Logging | Structured JSON with redaction; never secrets or raw PII |
| Trackers | Narrowest token scopes, only user-chosen repos |

## 8. Data protection

- Minimisation: only the chunks needed for a step go to a model.
- Retention per project (default 90 days); one-click project delete.
- PII masked in exports by default.
- Data-flow page in the app shows which provider got which data type.
- Designed to fit GDPR and Bangladesh's data-protection rules; confirm legal duties with the university before claiming compliance.

## 9. Supply chain

Lock files (uv/pnpm) · Renovate · `pip-audit`, `pnpm audit` · Ruff + Bandit, ESLint security, Semgrep · gitleaks on every commit · Trivy image scan, minimal pinned images · CycloneDX SBOM per release · cosign-signed runner images (v1) · branch protection (review + green CI).

## 10. OWASP LLM Top 10 mapping

| Risk | Control |
|---|---|
| Prompt injection | §4 layers 1–4, 7 |
| Sensitive info disclosure | Redaction, local model, secret placeholders |
| Supply chain | §9 |
| Data & model poisoning | Only approved nodes + verified citations feed expected results |
| Improper output handling | Schema validation, no exec of model text, sandboxed code |
| Excessive agency | Fixed tools, policy engine, gates, plan lock |
| System prompt leakage | No secrets in prompts |
| Vector/embedding weaknesses | Per-project partitions, access checks on retrieval |
| Misinformation | Cited ground truth, quote check, Unable to Verify |
| Unbounded consumption | Budgets, step limits, rate limits, cost meter |

## 11. Security testing & incident response

- Unit tests: policy + permissions at 100% branch coverage.
- Red-team injection suite in CI; OWASP ZAP baseline in CI.
- OWASP ASVS L1 checklist before demo; L2 for v1.
- Incident runbook: revoke runner certs (`saq runner revoke <id>`), rotate model/tracker keys, invalidate sessions, notify users, write post-mortem in `docs/security/incidents/`.
