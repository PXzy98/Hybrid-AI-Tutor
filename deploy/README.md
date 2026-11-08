# Deployment (task Z8)

One Docker Compose stack (guide 4.2): `proxy` (Caddy), `api`, `worker` (the same image as `api`, started as
`python -m app.worker`) and `db` (PostgreSQL). The local model (vLLM or Ollama) runs elsewhere and is reached by
URL.

```
browser ──80/443──► proxy (Caddy: serves the frontend, forwards /api to api, HTTPS with a domain)
                     ├─ api      FastAPI
                     ├─ worker   live settings switch, background jobs
                     └─ db       PostgreSQL (internal network only)
```

- **Networks**: `public` (proxy, api, worker) and `internal` (`internal: true`: db, api, worker). Only the proxy
  publishes ports; the database is not reachable from outside the stack.
- **Local**: `docker compose up --build` → <http://localhost:8080> (plain HTTP). `docker-compose.override.yml` is
  loaded automatically and exposes the database on `127.0.0.1:5432` for a backend or tests on the host.
- **Production**: set `SITE_ADDRESS=<domain>`, `HTTP_PORT=80`, `HTTPS_PORT=443` and `POSTGRES_PASSWORD` in
  `.env`, then run only the main file, so the database is not exposed:

  ```bash
  docker compose -f docker-compose.yml up -d --build
  ```

  Caddy obtains and renews the certificate itself (ports 80 and 443 must reach the host); certificates are kept
  in the `caddy-data` volume.
- **Files**: `Caddyfile` (proxy and web server; security headers; no buffering for streamed answers),
  `proxy.Dockerfile` (builds the frontend and serves it with Caddy).
