# Deployment and operations (task Z14)

For whoever deploys and runs the tutor. It links to the detailed documents instead of repeating them:
[deploy/README.md](../deploy/README.md) (containers, proxy, metrics, CI scans), [DATABASE.md](DATABASE.md),
[MODEL_CONNECTIONS.md](MODEL_CONNECTIONS.md), [PRIVACY_PROFILES.md](PRIVACY_PROFILES.md); the state of the work and the open tasks: [HANDOVER.md](HANDOVER.md). Status:
2026-11-08; the last section lists what is not built yet.

## 1. What runs

| Service | What | Reached by |
|---|---|---|
| `proxy` | Caddy: serves the frontend, forwards `/api/*` to `api`, HTTPS with a domain name | the browser (ports 80/443) |
| `api` | FastAPI on port 8000: API v1 (current frontend) and v2; applies the database migrations at startup | the proxy; Prometheus at `/metrics` |
| `worker` | background jobs and the live settings switch | nothing (health check only) |
| `db` | PostgreSQL 16 | `api` and `worker` only (internal network) |

**Not in the stack**: the local model server (Ollama or vLLM). It runs on a machine that the course controls and
is reached by URL (`OLLAMA_URL`, or a model connection marked trusted local). Original student text and learner
profiles go only to such a connection (guide rule 2).

Volumes: `db-data` (database), `tutor-data` (uploaded materials and indexes), `caddy-data` (certificates).

## 2. Before the first deployment

- **Host**: Docker with Compose v2; ports 80 and 443 reachable from the internet, and a DNS name pointing to the
  host (Caddy obtains the certificate itself).
- **Local model**: an Ollama or vLLM server the course controls, reachable from the host.
- **`.env`**: copy `.env.example`. The file is git-ignored; keys and passwords live only there (rule 6).

| Variable | Needed | Notes |
|---|---|---|
| `POSTGRES_PASSWORD` | yes | database password; Compose refuses to start without it |
| `SITE_ADDRESS`, `HTTP_PORT=80`, `HTTPS_PORT=443` | production | the domain name turns on HTTPS |
| `AUTH__COOKIE_SECURE=true` | production | session cookie only over HTTPS |
| `INSTRUCTOR_USERNAME`, `INSTRUCTOR_INITIAL_PASSWORD` | first start | creates the first account (an **admin**), which must change its password at first login; remove both afterwards |
| `SETTINGS_ENCRYPTION_KEY` | before anyone saves a model connection with an API key | Fernet key; **keep a copy**: without it stored API keys cannot be read and the api refuses to start |
| `OLLAMA_URL`, `LLM__LOCAL__MODEL` | yes | the local model server and model |
| `CLOUD_BASE_URL`, `CLOUD_API_KEY`, `CLOUD_MODEL` | optional | an external model; leave the key empty for local-only |
| `SPACY_MODEL` | optional | `en_core_web_lg` (default) for production |

Limits (usage, login failures, roster size, invitation codes, uploads) are in `config.yaml` under `limits`; any
value can be overridden in `.env` as `SECTION__FIELD`, for example `LIMITS__ACCOUNTS__LOGIN_FAILURES_PER_HOUR=20`.

## 3. Deploy

```bash
git clone https://github.com/PXzy98/Hybrid-AI-Tutor.git && cd Hybrid-AI-Tutor
cp .env.example .env   # then fill in section 2
docker compose -f docker-compose.yml up -d --build
docker compose ps      # all services healthy
curl -fsS https://<domain>/api/v1/health
```

Use only `docker-compose.yml` in production: `docker-compose.override.yml` is the local-development file that
publishes the database on `127.0.0.1:5432`.

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
docker compose -f docker-compose.yml up -d --build
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

## 9. Not built yet (2026-11-08)

| Missing | Effect for operations | Task |
|---|---|---|
| End of term and its export | student data of a finished course cannot be exported and deleted through the API yet; do not archive by deleting rows by hand | Z9 (needs per-course learner data, S) |
| Usage limits enforced on questions | counters and limits exist; the ask endpoints do not call them yet | v2 ask |
| Frontend for API v2 | the current frontend uses API v1 and the demo course; course management is API-only for now | T6, T7 |
| Deployment on the test host; an alert receiver; the vLLM address for scraping | the monitoring stack is ready but not started anywhere yet | Z13 part 2 |
| Measured capacity on the real vLLM server | sizing is not confirmed; `eval/load-test/run.py` is ready | Z6 load test |
