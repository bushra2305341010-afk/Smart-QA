#!/bin/sh
# Post-deploy smoke test: TLS, SPA, API health/readiness, OpenAPI, security headers.
#   deploy/scripts/smoke.sh https://qa.example.com
set -eu
URL="${1:?usage: smoke.sh https://host}"
fail() { echo "SMOKE FAIL: $*" >&2; exit 1; }
curl -fsS "$URL/api/v1/healthz" | grep -q '"ok"' || fail "healthz"
curl -fsS "$URL/api/v1/readyz" | grep -q '"ready"' || fail "readyz (database/redis)"
curl -fsS "$URL/" | grep -qi '<div id="root"' || fail "web app"
curl -fsS "$URL/api/v1/openapi.json" | grep -q '"/api/v1/runner/jobs/pull"' || fail "openapi"
curl -fsSI "$URL/" | grep -qi '^strict-transport-security' || fail "HSTS header"
curl -fsSI "$URL/" | grep -qi '^content-security-policy' || fail "CSP header"
echo "smoke OK: $URL"
