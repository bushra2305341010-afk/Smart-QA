# Web UI build + Caddy (TLS, static SPA, reverse proxy to the API, runner mTLS listener).
FROM node:20.18-alpine AS build
WORKDIR /web
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
# The pnpm version pinned in package.json "packageManager" (corepack in Node 20.18 cannot
# verify current pnpm signatures, so install it with npm instead).
RUN npm install -g "pnpm@$(node -p "require('./package.json').packageManager.split('@')[1]")" \
    && pnpm install --frozen-lockfile
COPY apps/web ./
RUN pnpm build

FROM caddy:2.8.4-alpine
COPY --from=build /web/dist /srv
COPY deploy/Caddyfile /etc/caddy/Caddyfile
