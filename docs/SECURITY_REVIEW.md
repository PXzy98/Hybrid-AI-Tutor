# Security review (task Z27, 2026-11-19)

Scope: the whole system before it goes public on Prof. Abbas's AWS (v5 V10) with a public vLLM for the demo
(V12). Reviewed on `main` at the state of 2026-11-19 plus the open v5 branches (V1 to V15). Method: code
reading of every area the task lists, an inventory of the access dependency of every `/api/v2` route, the
upload, SSRF and prompt paths, the proxy and Compose files, `npm audit`, and a search of the whole git history
for key-like strings.

Risk: **High** = a student's data or the system can be taken over by someone with an account; **Medium** = a
weakness that needs another mistake or an insider; **Low** = defence in depth. Every finding has an owner and a
state.

## Summary

| ID | Finding | Risk | Owner | State |
|---|---|---|---|---|
| H1 | API v1 `PUT /admin/config`: any instructor could change system-wide settings, including the trusted local model address (which receives every course's original student text) and the answer checkers | High | Z | **fixed in this PR** |
| M1 | API v1 `POST /admin/llm-server/test`: any instructor could make the server connect to arbitrary private addresses (internal network probing) | Medium | Z | **fixed in this PR** |
| M2 | API v1 instructor routes are scoped to the demo course only by convention: any instructor reads the demo course's class summary, request logs (sanitized questions) and materials | Medium | Z | open: turn API v1 off in production (task below) |
| M3 | `auth.cookie_secure` is `false` by default; a production deploy that forgets `AUTH__COOKIE_SECURE=true` sends the session cookie over HTTP before the HTTPS redirect | Medium | Z | open: V10 deploy checklist; make the production Compose file set it |
| M4 | The demo vLLM (V12) will be on the internet: without `--api-key` anyone could use it, and it receives original student text | Medium | Z | open: V12 runbook requires the key, HTTPS and one open port |
| L1 | `react-router-dom` 6.x: two moderate advisories (open redirect via a backslash in `Link`/`useNavigate`, SSR hydration). The app never navigates to an address taken from user input and has no SSR, so neither is reachable | Low | T | open: upgrade to a fixed release |
| L2 | `katex` (through `rehype-katex`): low advisory, prototype pollution that bypasses `trust`; the app never enables `trust` | Low | T | open: upgrade with L1 |
| L3 | `transformers` is held below 5 (CI advisories on 4.x concern loading untrusted model files); models are loaded with `local_files_only` from the deployment's own cache | Low | T | open (TODO "Dependencies") |
| L4 | Answer prompt: course material and web results were not named as data in the base rules (draft prompts already said so) | Low | Z | **fixed in this PR** (base rule 5) |
| L5 | CSP `style-src 'unsafe-inline'` (KaTeX and the UI library set style attributes) | Low | T | accepted: scripts stay `'self'` only |

No real secret was found in the history: the key-like strings are test fixtures (`sk-proj-FAKEfake`,
`sk-test-...`, `sk-kidney-disease`) and the AWS documentation key `AKIAIOSFODNN7EXAMPLE`.

## Areas

### Authentication and sessions
- Passwords: Argon2 (`argon2-cffi` defaults), at least 10 characters, temporary passwords must be changed at the
  first login, failed logins lock the account (`max_failed_logins`, `lockout_minutes`) and are limited per
  client address (`login_failures_per_hour`), as are invitation joins (`join_attempts_per_hour`).
- Sessions: a random token in an `HttpOnly`, `SameSite=Lax` cookie, 12 hours, revoked on logout, on a password
  reset and when an account is deactivated (V9). `Secure` depends on M3.

### CSRF
Every unsafe `/api/v2` request needs `X-CSRF-Token`: derived from the HttpOnly session token after login (another
site can neither read nor compute it), a double-submit cookie before login. API v1 relies on `SameSite=Lax` only;
see M2.

### Role checks (rules 3 and 9)
Every `/api/v2` route was listed with the dependencies FastAPI resolves for it: all routes require a logged-in
user and a course role (`require_course_role`) or a system role (`require_system_role`), except `GET
/auth/csrf`, `POST /auth/login`, `POST /auth/logout` and `POST /auth/join`, which are public by design. New v5
routes have access tests (another course's instructor, another student, logged out). The frontend decides no
permission (statistics-only UI follows `CourseOut.individual_view`; the backend refuses anyway, V1).

API v1 is frozen and serves only the demo course; `require_instructor` lets every instructor and admin in (H1,
M1 fixed here; M2 remains).

### SSRF
- Model connections: `app.llm.ssrf` checks the address when it is saved and pins the resolved address at every
  call (`PinnedTransport`); external connections must be public, link-local and the system's own services are
  never allowed. The deployment's `VLLM_KEY` is only sent to its own vLLM (PR #107).
- Web search: the provider URLs go through the same check; queries come only from `search_query()` (rule 5).
- Web pages as material (V7): `app.rag.web_pages.fetch_page` is the only fetcher of an address an instructor
  names: https only, no credentials, public addresses only, pinned per request (a name that rebinds to a private
  address is refused), every redirect checked (at most 3), 2 MB, 15 s, HTML/text only; tested against
  loopback, 10/8, 172.16/12, 192.168/16, 169.254.169.254, IPv6 loopback and link-local, `0.0.0.0`, redirects
  to private and to http.

### Uploads
- Materials, AI-draft uploads (V6) and web pages (V7) are scanned with `scan_document()` before anything is
  stored; refusals name finding types, never text. The Z25 fix makes the scan stop refusing public course text
  (0 of the 304 open-pack files) without changing E6.
- Size limits: 25 MB at the proxy, the material limit in the API, 64 MB unpacked and 10 000 members for DOCX and
  PPTX (zip bombs), 250 pages or slides, a 2 million character course budget; content ZIP imports read only the
  seed files, in memory, with per-file and total limits and no path outside the folder.

### Prompt injection
- Answer prompts: base rule 5 (this PR) says material, web results and earlier messages are data, never
  instructions. Draft prompts already said so.
- Instructor guidelines (Z26) are instructions by design, bounded below the safety rules; the student's own
  instruction (V15) is last and yields to both; a student's "ignore the instructor" stays in the question.
- Web results reach only the cloud path through the allow-listed request; the cloud never receives the learner
  profile or the student's own instruction (rule 2).

### Stored keys and secrets
Model connection keys are encrypted with `SETTINGS_ENCRYPTION_KEY` and never returned (only the last four
characters); invitation codes likewise. Keys live in the server `.env` only (rule 6); no secret is in the
repository or its history (search above).

### Proxy, TLS and networks
- Caddy: automatic HTTPS for a domain, HSTS, a strict CSP (scripts from the origin only), `X-Frame-Options DENY`,
  `frame-ancestors 'none'`, `nosniff`, a referrer and a permissions policy, no `Server` header, admin API off.
- Compose: two networks; the database is on the `internal` network only (no internet, no published port in
  production); the worker and API have no published port; Grafana is bound to `127.0.0.1`; `/metrics` is not
  routed by the proxy.

### Logs and stored text (rule 1)
`privacy.log_raw_text` cannot be switched on. `request_log` and conversations keep the **sanitized** question
(placeholders instead of personal values); application logs carry request ids, not text. The end of term deletes
the course's request logs and conversations; deleting an account anonymizes its log rows.

### Dependencies and images
`npm audit --omit=dev`: 0 high or critical, 2 moderate (L1), 4 low (L2). Python: CI advisories on `transformers`
4.x (L3). Images are built from the repository's Dockerfiles on official base images; a container scan (for
example Trivy) is part of the V10 deploy checklist.

## Fixes in this PR
- H1: in API v1 `PUT /admin/config` an instructor may only change the demo course's routing fields
  (`routing_threshold`, `show_routing_progress`); any system-wide field needs an administrator (HTTP 403).
- M1: API v1 `POST /admin/llm-server/test` is for administrators only.
- L4: base rule 5 in `app/prompts/base_system.md`.
- Tests: `test_admin_dashboard.py` runs the dashboard as an administrator and checks that an instructor gets 403
  for a system field and for a server test, while the demo course's routing fields still work.

## Before the public deployment (V10, V12)
1. Turn off API v1 in production, or restrict it to administrators (M2); the v2 frontend does not use it.
2. Production Compose file: `AUTH__COOKIE_SECURE=true` and a domain in `SITE_ADDRESS` (M3).
3. vLLM on RunPod or forwarded: `--api-key` set and equal to `VLLM_KEY`, HTTPS in front, only the API port open,
   `VLLM_BASE_URL` pointing at it (M4).
4. Upgrade `react-router-dom` and `katex` (L1, L2); run a container scan of the built images.
5. Re-run this review's route inventory after the last v5 merge.
