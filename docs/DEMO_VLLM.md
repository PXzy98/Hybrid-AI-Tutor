# The local model for the demo (task V12)

For the video and Design Day the production site needs a vLLM it can reach over the internet. Two ways, both
with the same rules. The decision is Z's (2026-11-17); the cost options for later are in
[GPU_COST.md](GPU_COST.md).

## Rules (both ways)

1. **A key is required.** vLLM runs with `--api-key <VLLM_KEY>`; a request without it gets HTTP 401. The key is a
   new random value (for example `python -c "import secrets; print(secrets.token_urlsafe(32))"`), stored only in
   the production server's `.env` (`VLLM_KEY`) and in the vLLM start command, never in the repository, chat or
   e-mail. The app sends it only to its own `VLLM_BASE_URL` (PR #107).
2. **HTTPS only.** The address in `VLLM_BASE_URL` starts with `https://`.
3. **Only the API port is reachable**, and only through HTTPS: no SSH or Jupyter port open to everyone, no vLLM
   metrics port, nothing else on the machine published.
4. **What it receives.** The deployment's local model is a *trusted local* connection: it gets original
   student text and learner profiles (rule 2). For the demo only fictional accounts and the open course packs
   are used. Real students' data needs the client's approval of the host first (a Canadian data centre, the
   provider's terms), the same as for the AWS deployment.
5. **After the demo:** stop the pod or close the forward, and change the key.

## Way A: vLLM on RunPod

1. Create a pod with one GPU of at least 24 GB (an RTX 4090, L4, A5000 or better for Qwen3.5-9B at bf16 with a
   16k context); pick a data centre in Canada if one has the GPU, otherwise the nearest in North America.
2. Image `vllm/vllm-openai` (a fixed version tag, the one the lab server runs). Expose **only** port 8000 as an
   HTTP port; RunPod serves it at `https://<pod-id>-8000.proxy.runpod.net` with TLS. Do not expose the SSH TCP
   port publicly (use the web terminal if needed).
3. Start command (the container arguments):
   ```
   --model Qwen/Qwen3.5-9B --served-model-name Qwen3.5-9B --api-key ${VLLM_KEY} --max-model-len 16384 --gpu-memory-utilization 0.90
   ```
   with `VLLM_KEY` as a pod environment variable (RunPod secrets), not typed into the command.
4. On the production server `.env`: `VLLM_BASE_URL=https://<pod-id>-8000.proxy.runpod.net/v1` and `VLLM_KEY=...`;
   restart the API and the worker (`docker compose up -d api worker`).

## Way B: the lab vLLM, forwarded

The lab server (192.168.x, the vLLM the team uses) is not reachable from the internet. Do not forward its port
8000 on the router as plain HTTP. Instead, put an HTTPS endpoint in front of it:
- **A tunnel** (Cloudflare Tunnel or Tailscale Funnel) from the lab machine to `localhost:8000`: no port is
  opened on the router, the tunnel provides HTTPS, and only that one service is published. Preferred.
- **Or a reverse proxy** on the lab machine (Caddy with a domain name and automatic HTTPS) and the router
  forwarding only 443 to it; the proxy forwards only `/v1/*` to vLLM.

vLLM itself still runs with `--api-key`, so the tunnel or proxy is not the only lock. Then set `VLLM_BASE_URL`
to the public `https://.../v1` address and `VLLM_KEY` as in way A.

## Check before the demo

```
curl -s -o /dev/null -w "%{http_code}\n" https://<address>/v1/models                                  # 401: the key is required
curl -s -H "Authorization: Bearer $VLLM_KEY" https://<address>/v1/models | python -m json.tool | head      # lists Qwen3.5-9B
```
Then in the app: **Administration** > model connections, test the deployment's local model; ask one question
in a demo course and check the answer is labelled **Local model**. Keep the GPU running during the whole demo
slot (a cold start downloads about 18 GB of weights).
