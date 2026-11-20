# Deployment and operations (task Z14)

For whoever deploys and runs the tutor. It links to the detailed documents instead of repeating them:
[deploy/README.md](../deploy/README.md) (containers, proxy, metrics, CI scans), [DATABASE.md](DATABASE.md),
[MODEL_CONNECTIONS.md](MODEL_CONNECTIONS.md), [PRIVACY_PROFILES.md](PRIVACY_PROFILES.md); the state of the work and the open tasks: [HANDOVER.md](HANDOVER.md). Status:
2026-11-17; the last section lists what is not built yet.

## 1. What runs

| Service | What | Reached by |
|---|---|---|
| `proxy` | Caddy: serves the frontend, forwards `/api/*` to `api`, HTTPS with a domain name | the browser (ports 80/443) |
| `api` | FastAPI on port 8000: API v2 (the frontend) and the frozen API v1; applies the database migrations at startup | the proxy; Prometheus at `/metrics` |
| `worker` | background jobs and the live settings switch | nothing (health check only) |
| `db` | PostgreSQL 16 | `api` and `worker` only (internal network) |

**Not in the stack**: the local model server (vLLM). It runs on a machine that the course controls and is
reached by URL (`VLLM_BASE_URL` with `VLLM_KEY`, or a model connection marked trusted local). Original student text and learner
profiles go only to such a connection (guide rule 2).

Volumes: `db-data` (database), `tutor-data` (uploaded materials and indexes), `caddy-data` (certificates).

## 2. Before the first deployment

- **Host**: Docker with Compose v2; ports 80 and 443 reachable from the internet, and a DNS name pointing to the
  host (Caddy obtains the certificate itself).
- **Local model**: a vLLM server the course controls, reachable from the host, serving the model under the
  name of `llm.local.model` (`--served-model-name Qwen3.5-9B`) and protected by `--api-key`.
- **`.env`**: copy `.env.example`. The file is git-ignored; keys and passwords live only there (rule 6).

| Variable | Needed | Notes |
|---|---|---|
| `POSTGRES_PASSWORD` | yes | database password; Compose refuses to start without it |
| `SITE_ADDRESS`, `HTTP_PORT=80`, `HTTPS_PORT=443` | production | the domain name turns on HTTPS |
| `AUTH__COOKIE_SECURE=true` | production | session cookie only over HTTPS; `docker-compose.prod.yml` sets it |
| `INSTRUCTOR_USERNAME`, `INSTRUCTOR_INITIAL_PASSWORD` | first start | creates the first account (an **admin**), which must change its password at first login; remove both afterwards |
| `SETTINGS_ENCRYPTION_KEY` | before anyone saves a model connection with an API key | Fernet key; **keep a copy**: without it stored API keys cannot be read and the api refuses to start |
| `VLLM_BASE_URL`, `VLLM_KEY` | yes | the local model server: its OpenAI-compatible API root ending in `/v1`, and its `--api-key`; without the URL no local answers |
| `LLM__LOCAL__MODEL`, `LLM__UNDERSTAND__MODEL` | optional | the model name the server lists under `/models` (default `Qwen3.5-9B`) |
| `CLOUD_BASE_URL`, `CLOUD_API_KEY`, `CLOUD_MODEL` | optional | an external model; leave the key empty for local-only |
| `SPACY_MODEL` | optional | `en_core_web_lg` (default) for production |
| `WEBSEARCH__PROVIDER`, `OPENAI_API_KEY`, `TAVILY_API_KEY`, `SEARXNG_SECRET` | optional | web search for cloud answers: `openai` (default, with `OPENAI_API_KEY`), `api` (with `TAVILY_API_KEY`), `searxng` (no key; the secret and `--profile searxng`) or `off`; [WEB_SEARCH.md](WEB_SEARCH.md) |

Limits (usage, login failures, roster size, invitation codes, uploads) are in `config.yaml` under `limits`; any
value can be overridden in `.env` as `SECTION__FIELD`, for example `LIMITS__ACCOUNTS__LOGIN_FAILURES_PER_HOUR=20`.

## 3. Deploy

```bash
git clone https://github.com/PXzy98/Hybrid-AI-Tutor.git && cd Hybrid-AI-Tutor
cp .env.example .env   # then fill in section 2
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose ps      # all services healthy
curl -fsS https://<domain>/api/v1/health
```

Use only `docker-compose.yml` plus `docker-compose.prod.yml` in production (always `-f` both):
`docker-compose.override.yml` is the local-development file that publishes the database on `127.0.0.1:5432`.
The production file sets `AUTH__COOKIE_SECURE=true` and `API__V1_ENABLED=false` (API v1 is frozen, serves only the
demo course and is not used by the web app; `/api/v1/health` keeps answering for the health checks), and Compose
refuses to start without `SITE_ADDRESS` (the domain). Because the api starts with a log warning
(`deployment: ...`) when `SITE_ADDRESS` is a domain and the cookie is not secure, or when `VLLM_BASE_URL` points
outside the host's network without `https` or without `VLLM_KEY`, check `docker compose logs api | grep deployment`.

**Deploy checklist** (security review, M2 to M4):
- [ ] `SITE_ADDRESS` is the domain, `HTTP_PORT=80`, `HTTPS_PORT=443` (HTTPS certificate obtained: `curl -I https://<domain>`).
- [ ] Started with both Compose files; `curl -i https://<domain>/api/v1/topics` answers 404 and `https://<domain>/api/v1/health` answers 200.
- [ ] The login response sets the cookie with `Secure` (browser developer tools or `curl -i`).
- [ ] The vLLM runs with `--api-key` equal to `VLLM_KEY`, `VLLM_BASE_URL` starts with `https://`, and only the API port is open ([DEMO_VLLM.md](DEMO_VLLM.md)).
- [ ] `docker compose logs api | grep deployment` prints nothing.

**First login**: sign in with `INSTRUCTOR_USERNAME` and the initial password, change the password, then remove
both variables from `.env`. This admin then:
1. creates instructor accounts (`POST /api/v2/admin/instructors`; each gets a one-time temporary password);
2. adds model connections (`/api/v2/admin/model-endpoints`; a trusted-local connection needs the "I control
   this service" confirmation) and sets the defaults in the system settings;
3. sets the enabled course types in the system settings (default: every privacy profile).

Instructors then create courses, import the class list (CSV with an `email` column), rotate the invitation code
and share it with the class. The code is shown once; rotating it again makes a new one.

## 4. Upgrade

```bash
docker compose exec -T db pg_dump -U tutor -d tutor -Fc > backup-$(date +%F).dump   # section 5
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

The api upgrades the schema to the newest migration at startup, under a lock, so several api processes can
start together (DATABASE.md). The worker waits until the api is healthy. Settings that users saved are never
overwritten by a deploy: a new `config.yaml` default applies only where nothing was saved.

## 5. Backup and restore

- **Database**: the command in section 4, daily (cron) and before every upgrade. Keep copies off the host.
- **Restore** into a stopped stack:

  ```bash
  docker compose -f docker-compose.yml stop api worker
  docker compose exec -T db pg_restore -U tutor -d tutor --clean --if-exists < backup-YYYY-MM-DD.dump
  docker compose -f docker-compose.yml start api worker
  ```

- **Files**: the `tutor-data` volume (materials and indexes; indexes can be rebuilt from the materials).
- **`.env`**: keep `SETTINGS_ENCRYPTION_KEY` and `POSTGRES_PASSWORD` in the course's password manager. A
  database backup without the encryption key has unreadable API keys (connections must be re-entered).

## 6. Monitoring

| What | How |
|---|---|
| Up | `GET /api/v1/health` through the proxy; container health checks (`docker compose ps`) |
| Metrics | Prometheus scrapes `http://api:8000/metrics` inside the stack (requests and durations by route template, component and content versions; deploy/README.md) |
| A settings change being applied | `GET /api/v2/admin/settings/apply-status`: state, target version, live processes and their versions. A change not applied everywhere within `limits.settings.apply_timeout_seconds` is rolled back by itself |
| Logs | `docker compose logs api worker`. They never contain question text (`privacy.log_raw_text` cannot be switched on) |

Prometheus, alert rules and Grafana are ready to start (`--profile monitoring`, deploy/README.md); vLLM is scraped once its address is in `deploy/monitoring/targets/vllm.yml`. No alert receiver is chosen yet.

## 7. Routine tasks and incidents

| Situation | What to do |
|---|---|
| An instructor forgot the password | admin: `POST /api/v2/admin/instructors/{id}/reset-password` (temporary password, all sessions end) |
| The only admin is locked out | on the host: `docker compose exec api python -m app.auth.cli set-password <username>` (also clears the lockout and ends all sessions) |
| A student forgot the password | the course instructor: `POST /api/v2/courses/{id}/members/{member_id}/reset-password` |
| Someone else may have the invitation code | the instructor rotates it (`POST .../invite/rotate`); the old code stops working at once |
| The term is over | the instructor: `POST /api/v2/courses/{id}/end-term` with `{"confirm": true}`. It writes an export (ZIP: class summary; in visibility mode B also the overviews the instructor may see) and then deletes the students' memberships and their data in that course. Download: `GET .../exports/{export_id}` for `limits.courses.export_retention_hours` (72). Files: `courses/<id>/exports/` in the `tutor-data` volume |
| A student gets 429 on questions | `limits.usage` per student and course (API v2). At the daily cloud limit the answers come from the local model |
| A settings change made things worse | restore an earlier entry: `POST /api/v2/admin/settings/restore/{history_id}` (or the course's) |
| Settings show 423 `settings_applying` for long | see apply-status; it rolls back at the timeout. A process that never reports runs the old version: restart it |
| Many 429 on login | `limits.accounts.login_failures_per_hour` per client address. The api image starts uvicorn with `--proxy-headers`, so the address is the one Caddy reports; uvicorn started another way needs the same flag, or all users share the proxy's address |
| A CI security scan fails | a new advisory or finding: fix it, or add it with its reason and owner to `backend/.pip-audit-ignore` / `backend/.bandit-baseline.json` (deploy/README.md) |

## 8. Privacy duties of whoever runs it

- Only fictional data goes to hosted model APIs during development and tests; real student questions reach an
  external model only through the cloud gate (rule 2).
- After any change to privacy rules or profiles, run E6 (`eval/privacy-filter/`) and do not ship a result that is
  worse (rule 4); E4 (`eval/privacy-audit/run.py --smoke`) runs in CI and fails on any leak.
- Do not copy database dumps to personal machines; they contain learner profiles (pseudonymous) and account data.

## 9. Not built yet (2026-11-17)

| Missing | Effect for operations | Task |
|---|---|---|
| Deployment on the test host; an alert receiver; the vLLM address for scraping | the monitoring stack is ready but not started anywhere yet | Z13 part 2 |
| Measured capacity of the app on the real servers | the model connection was measured through the gateway (0.40 answers/s alone, 0.71 at 8 at a time, no gain at 20); tokens per second and the app under load were not; `eval/load-test/run.py` is ready | Z23 |
| A health check for vLLM | `/api/v1/health` asks Ollama's `/api/tags`; a vLLM-only deployment shows the local model as unreachable although answers work | audit I6 |
| A vLLM connection in the deployment's configuration | a vLLM-only deployment needs an administrator to add a trusted local connection after the first start (`MODEL_CONNECTIONS.md`) | audit A4 |
