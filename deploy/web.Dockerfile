# Web UI build + Caddy (TLS, static SPA, reverse proxy to the API, runner mTLS listener).
FROM node:20.18-alpine AS build
WORKDIR /web
RUN corepack enable
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY apps/web ./
RUN pnpm build

FROM caddy:2.8.4-alpine
COPY --from=build /web/dist /srv
COPY deploy/Caddyfile /etc/caddy/Caddyfile
