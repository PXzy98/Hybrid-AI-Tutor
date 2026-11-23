# Model connections and the model gateway (task Z6)

Every model call goes through the **model gateway** (`backend/app/llm/gateway.py`, `services.gateway`). It picks
the connection for the role, checks it, and queues the request.

## Which connection answers

| Role | Course connection | System default | Otherwise |
|---|---|---|---|
| `local` (original text, learner profile) | `course_settings.local_endpoint_id` | `system_settings.default_local_endpoint_id` | the deployment's vLLM (`VLLM_BASE_URL`, `VLLM_KEY` / `llm.local`), trusted local |
| `cloud` (only what passed the cloud gate) | `course_settings.cloud_endpoint_id` | `system_settings.default_cloud_endpoint_id` | `CLOUD_BASE_URL` / `CLOUD_MODEL` / `CLOUD_API_KEY` |

The small local calls on the original text use the `local` connection too (task Z17): the understand step
(knowledge components, question type), the hypothetical rewrite of a personal health question
(`health_detail_policy: generalize`) and the second health check (`privacy.llm_check`, on by default since Z22d). With a stored
connection they share its queue with the answers; a stored `local` connection that is not `trusted_local` is
never used for them (understand is skipped, the question stays local). Without one they use the deployment's
clients (`llm.understand`, `llm.local`). Checked on 2026-11-16 against vLLM (Qwen3.5-9B, thinking off):
understand 1 to 2 s, rewrite 0.8 s, health check 0.3 s.

## Rules

- **Trust**: a connection is `trusted_local` (may receive original student text; the creator confirms that he
  controls the service) or `external` (only the sanitized cloud request). A local role must use a trusted local
  connection and a cloud role an external one; the settings refuse anything else, and the gateway raises
  `TrustViolation` if trusted content would reach an external connection.
- **Local-only courses** (`local_only`): no external connection is used, ever.
- **SSRF**: at save time and before every call (`app/llm/ssrf.py`): http(s) only, no credentials in the URL, never
  link-local (cloud metadata), multicast, unspecified or reserved addresses, never the system's own services
  (`db`, `api`, `web`, `worker`, `proxy`, ... and their addresses); external connections also never private or
  loopback addresses.
- **API keys**: encrypted with `SETTINGS_ENCRYPTION_KEY` (Fernet, `.env`), shown only as the last four
  characters; the app does not start when stored keys cannot be decrypted.
- **Saving needs a successful connection test**; every create, change and delete is in `audit_log`. Deleting a
  connection sets the settings that used it back to the next layer.
- **Queue**: at most `limits.models.max_concurrent` requests per connection at a time; a request that waits
  longer than `limits.models.queue_timeout_seconds` gets "the model is busy".
- **Streaming**: `gateway.complete(..., stream=True)` returns the answer token by token (Ollama and
  OpenAI-compatible APIs).
- **Thinking off**: Qwen3.5 thinks before it answers unless told not to (on the vLLM test host a one-sentence
  answer took 9.9 s instead of 1.4 s). Ollama connections send `think: false`; trusted local OpenAI-compatible
  connections (vLLM) send `chat_template_kwargs: {"enable_thinking": false}`. External connections send neither,
  since hosted APIs reject unknown fields.
- **Structured answers** (understand, instructor AI drafts): Ollama gets the JSON schema as `format`; trusted local
  OpenAI-compatible connections (vLLM) get it as `response_format: json_schema`, so the server constrains the
  answer to it (with only `json_object` the model made up its own field names; #99). External connections get
  `json_object`. A caller may ask for more output tokens than the connection's limit for one call
  (`gateway.complete(..., max_tokens=...)`); structure drafts ask for 4,096.

## API

`/api/v2/admin/model-endpoints` (admin) and `/api/v2/courses/{course_id}/model-endpoints` (instructors of the
course): list, create, change, delete. Responses never contain the key.

## Load test

`eval/load-test/run.py` sends fictional questions through the gateway and reports throughput, latency and time to
the first token. Run it against the vLLM server from a machine that can reach it:

```bash
python eval/load-test/run.py --kind openai_compat --base-url http://<vllm-host>:8000/v1 --model Qwen3.5-9B --concurrency 20 --requests 200 --stream
```

`--model` is the served name that the server lists at `/v1/models`. CI runs it with `--smoke` (a fake model).
