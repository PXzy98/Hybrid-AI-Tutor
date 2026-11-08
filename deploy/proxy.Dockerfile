# Proxy image (task Z8): the built frontend served by Caddy, which also forwards /api to the api service.
#   docker build -f deploy/proxy.Dockerfile -t tutor-proxy .
FROM node:20-slim AS build
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npm run build

FROM caddy:2.8-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /web/dist /srv
EXPOSE 80 443
