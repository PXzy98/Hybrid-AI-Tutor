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

## Monitoring and security scans (task Z13, part 1)

**Metrics.** The api container serves Prometheus metrics at `GET /metrics` (port 8000 inside the stack). The
api publishes no port on the host and the web proxy forwards only `/api/*`, so `/metrics` is not reachable from
outside. A Prometheus container in the stack scrapes `http://api:8000/metrics`:

| Metric | Labels | Meaning |
|---|---|---|
| `tutor_http_requests_total` | `method`, `route`, `status` | requests by route template (`/api/v2/courses/{course_id}`), never by ID |
| `tutor_http_request_duration_seconds` | `method`, `route` | request duration histogram |
| `tutor_component_version` | none | system settings version the process runs (course-structure.md 6.5) |
| `tutor_content_version` | none | content version of the served course |
| `tutor_process_component_version` | `process`, `kind` | settings version of every live api and worker process (from their heartbeats; the worker has no `/metrics` of its own) |

Values are per process; with several uvicorn workers, scrape each one or sum them. Prometheus, alerts and
Grafana: the next section.

**Scans in CI** (`.github/workflows/ci.yml`):

| Scan | Where | Fails the build when |
|---|---|---|
| `bandit` (code, medium and high) | backend job | a finding not in `backend/.bandit-baseline.json` |
| `pip-audit` (installed Python packages) | backend job | an advisory not in `backend/.pip-audit-ignore` |
| `npm audit` (production dependencies) | frontend job | a high or critical advisory |
| `npm audit` (development tools) | frontend job | never (report only) |
| Trivy (built images, HIGH and CRITICAL with a fix) | docker job | never (report only) |

Every entry in the baseline and the ignore list has its reason and its owner. Remove an entry when its fix is
merged.

## Prometheus, alerts and Grafana (task Z13, part 2)

Files in `deploy/monitoring/`; the services are in `docker-compose.yml` under the profile `monitoring`, so they
start only when asked:

```bash
# in .env: GRAFANA_ADMIN_PASSWORD=<a long password>   (Grafana refuses to start without it)
docker compose -f docker-compose.yml --profile monitoring up -d
ssh -L 3000:127.0.0.1:3000 <host>    # then open http://localhost:3000 (user admin)
```

| File | What |
|---|---|
| `prometheus.yml` | scrapes `api:8000/metrics` every 15 s; vLLM from `targets/vllm.yml` |
| `targets/vllm.yml` | the vLLM server(s) as `host:port` (empty until the test host exists; reloaded by itself) |
| `alerts.yml` | api down, more than 5% server errors, 95th percentile above a minute, more than 50 failed logins in 10 minutes, live processes (api and worker) on different settings versions, vLLM down, more than 10 requests waiting for vLLM |
| `alertmanager.yml` | no receiver yet: alerts show in Alertmanager and Prometheus; add e-mail or Teams there once chosen |
| `grafana/` | the Prometheus data source and the "Tutor overview" dashboard (requests, errors, durations, failed logins and limits, settings versions, vLLM queue and tokens) |

Only Grafana publishes a port, on `127.0.0.1` of the host. Prometheus keeps 30 days. CI checks the files with
`promtool` and `amtool`, and `backend/tests/test_monitoring_config.py` checks that every metric they use exists.
