# Local model hosting: capacity per class size and GPU choice (task V13, for Prof. Abbas by 12/1)

PACT needs one GPU server for its local model (vLLM, Qwen3.5-9B): every question with personal data, every
learner-profile prompt and all course material go there, never to a cloud model. This report says how many
students one GPU serves, measured on the lab server through the whole app, and which GPU to buy or rent for a
class of a given size. Prof. Abbas set no fixed budget but asked for the cost to be justified.

Measured: the lab server (one NVIDIA RTX 5060 Ti 16 GB). Estimated: every other GPU, scaled from its memory
bandwidth (section 4). Prices are USD unless marked CA$, checked 2026-11-19 to 11-23 from public lists; check
the seller's own page before buying, prices change often (sources at the end).

**Short answer**

- One RTX 5060 Ti 16 GB answers about **45 to 49 questions a minute** through the whole app (privacy filter,
  routing, retrieval, the local model) with 32 students asking at once, none refused, slowest answer under
  50 s (fp8 KV cache, app limit 16 requests at once). A typical answer takes 10 to 25 s.
- That is enough for **one class of up to about 150 students** in normal use and in the busy evening before a
  deadline. A class of 200 at a deadline, or a whole class asked to "try the tutor now" in a lecture, needs
  about twice that: one faster card (RTX 5070 Ti / 5080 class, estimated) or a second 5060 Ti.
- **Several courses on one server add up**: plan the GPU for the sum of the classes that are active at the same
  time, not per course.
- Do not rent an L4 (AWS `g6`) for a class above about 100: its memory bandwidth (300 GB/s) is below the lab
  card's (448 GB/s), so it is estimated at about two thirds of the lab's throughput.

## 1. The lab server as measured

| Item | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 5060 Ti, 16 GB GDDR7, 448 GB/s |
| Server | vLLM 0.34.0 on the lab Unraid host |
| Model | `Qwen/Qwen3.5-9B`, weights in fp8 (`--quantization fp8`, about 9 GB), thinking off |
| vLLM options | `--max-model-len 16384 --gpu-memory-utilization 0.92 --max-num-seqs 16 --enable-prefix-caching --kv-cache-dtype fp8 --limit-mm-per-prompt '{"image":0,"video":0}'` |
| KV cache | 87,818 tokens with fp8 KV and vision off (26,300 tokens before, bf16 KV) |
| App settings (PR #161) | `llm.local.max_tokens` 2048, `llm.local.timeout_s` 120, `limits.models.max_concurrent` 8 (16 measured below), `queue_timeout_seconds` 60 |

One app request holds about 3,000 tokens of KV cache (about 1,000 of prompt with 4 course passages, up to 2,048
of answer). With bf16 KV the cache held about 8 such requests, which is why the server stopped getting faster at
8 at once. With fp8 KV and vision off it holds about 29; the server's `--max-num-seqs 16` is now the limit (60 %
of the cache in use at the peak of the load test).

## 2. Load through the whole app (measured)

`eval/load-test/app_load.py`: N fictional demo students, each with its own account and course (the eight open
course packs), ask 3 questions one after the other (S11 questions; 10 % of them ask for a long answer with a
table). A copy of the demo database, the local model only (no cloud, so no course text left), 2026-11-23.
Results: `eval/load-test/results/app_load_*`. Each level runs 1 to 3 minutes, so a single level varies by
about 20 % from run to run.

| Students asking at once | bf16 KV, app limit 4 (old) | bf16 KV, limit 8 | fp8 KV, limit 8 | fp8 KV, limit 16 |
|---|---|---|---|---|
| 8 | 18 a minute, slowest 40 s | 19, 28 s | 18, 35 s | 19, 33 s |
| 16 | 27, 54 s | 36, 40 s | 23, 63 s | 30, 41 s |
| 24 | 25, 60 s | 43, 42 s | 39, 40 s | 43, 41 s |
| 32 | 23, 92 s, **7 of 96 refused** | 45, 62 s | 38, 66 s | **49, 48 s** (p50 23 s) |

Every question asking for a long answer (the worst case):

| Students at once | bf16, limit 8 | fp8, limit 8 | fp8, limit 16 |
|---|---|---|---|
| 8 | 11 a minute, slowest 52 s | 12, 43 s | 11, 54 s |
| 16 | 15, 77 s | 15, 62 s | 20, 61 s |

Reading it:

- The app's old limit of 4 requests at once wasted the GPU and refused students at 32 at once. With 8 or 16
  nothing was refused.
- fp8 KV only pays off when the app sends more than 8 at once: with a limit of 16 the 32-student level answered
  49 a minute with the slowest answer at 48 s (bf16, limit 8: 45 and 62 s).
- Answer length decides the rate: about 45 to 49 a minute for ordinary questions, 15 to 20 when every question
  asks for a long answer.
- No answer was cut at 2048 tokens in the ordinary mix; 3 of 48 long-answer requests were cut with limit 16
  (the note "this answer reached the length limit" appears). 3072 tokens gave no benefit (#161).
- Answer quality with fp8 KV (`eval/load-test/results/fp8kv_answer_quality*`, local judge, 10 questions per
  pack, all 8 packs): 62 of 64 answerable questions correct, 2 partly, 0 wrong; grounded 2.0 of 2 in every pack;
  16 of 16 questions outside the material handled. The two packs with a bf16 baseline (6.002, CS50x) gave the
  same counts. A small, single-judge check, not a benchmark.

## 3. Class sizes

Assumptions (not measured; they set the demand): a student asks a question every 3 minutes while working with
the tutor. Three situations:

- **Normal week**: 20 % of the class works with the tutor in the same hour.
- **Deadline evening**: 50 % of the class at once, one question every 2 minutes.
- **Lecture burst**: the instructor says "ask the tutor now" and the whole class asks within one minute.

Capacity used below: 45 answers a minute for the lab 5060 Ti (the measured ordinary mix); a waiting request is
refused after 60 s (`queue_timeout_seconds`), so in a burst about the first 50 to 55 are answered within a
minute and a half (an estimate from the measured rate) and the rest are told the model is busy and must ask again.

| Class | Normal week (answers a minute needed) | Deadline evening | Lecture burst (questions at once) | One RTX 5060 Ti 16 GB |
|---|---|---|---|---|
| 30 | 2 | 8 | 30 | ample; a burst is answered within about 40 s |
| 60 | 4 | 15 | 60 | ample; a burst takes about 80 s, a few may be told to ask again |
| 100 | 7 | 25 | 100 | enough; a burst: about half answered at once, the rest within 2 to 3 minutes after asking again |
| 150 | 10 | 38 | 150 | enough for normal and deadline use (about 85 % of capacity at the deadline); bursts should be avoided |
| 200 | 13 | 50 | 200 | normal use fine; at a deadline above capacity (waits over a minute, some refusals): one faster card or a second 5060 Ti |

Several courses on one server: add their demand. Two classes of 100 with the same deadline evening are 50 a
minute, the same as one class of 200.

## 4. Other GPUs (estimated)

The local model writes one token at a time and reads all its weights (about 9 GB in fp8) for every token, so its
speed is set mostly by memory bandwidth. The memory size sets how many answers fit at once (the KV cache): with
fp8 weights and fp8 KV, a 16 GB card already holds about 29 answers, more than vLLM is set to run. The estimate
below scales the measured 45 answers a minute by the bandwidth ratio; real gains are usually somewhat lower
(compute and scheduling). Measure with `eval/load-test/capacity.py` and `app_load.py` before buying more than one.

| GPU | Memory | Bandwidth (GB/s) | Estimated vs the lab card | Price (new, Canada, Nov 2026, rough) | Note |
|---|---|---|---|---|---|
| RTX 4060 Ti 16 GB | 16 GB | 288 | about 0.6x | (previous generation) | slower than the lab card |
| **RTX 5060 Ti 16 GB** (lab) | 16 GB | 448 | **1x, measured** | CA$950 to 1,330 (list US$429) | serves one class up to about 150 |
| RTX 4080 Super | 16 GB | about 736 (spec, not checked) | about 1.6x | (previous generation) | |
| RTX 5070 Ti | 16 GB | 896 | about 1.7 to 2x | CA$1,090 to 2,200 (list US$749) | best price per throughput among new cards |
| RTX 5080 | 16 GB | 960 | about 1.8 to 2.1x | about CA$2,230 (list US$999) | little over a 5070 Ti for a higher price |
| RTX 4090 | 24 GB | 1,008 | about 1.9 to 2.2x | not priced here (previous generation) | more memory: room for a larger model later |
| RTX 5090 | 32 GB | 1,792 | about 3 to 4x | about CA$6,700 street (list US$1,999) | priced far above list; several classes on one card |

Rented GPUs (per hour, on demand):

| Provider and GPU | Bandwidth (GB/s) | Estimated vs the lab card | Price per hour | Class hours (172 h) / month | Note |
|---|---|---|---|---|---|
| AWS `g6.xlarge`, L4 24 GB, ca-central-1 | 300 | about 0.65x | about $0.89 | about $154 | same Canadian AWS account as the rest of PACT; enough for a class up to about 100 |
| RunPod, L4 24 GB | 300 | about 0.65x | $0.39 to 0.49 | $67 to 84 | provider outside the university |
| RunPod, A40 48 GB | about 696 (spec, not checked) | about 1.4x | $0.49 to 0.59 | $84 to 101 | |
| RunPod, L40S 48 GB | 864 | about 1.7x | about $1.09 | about $187 | |
| RunPod, RTX 4090 24 GB | 1,008 | about 2x | $0.69 to 0.89 (Secure), $0.34 (Community) | $119 to 153 | Community Cloud hosts are third parties: demo data only |
| RunPod, RTX 5090 32 GB | 1,792 | about 3x | $0.99 to 1.19 (Secure), $0.69 (Community) | $170 to 205 | |

## 5. Recommendation (to confirm with Prof. Abbas)

1. **One course of up to about 150 students** (ELG 5902 and similar): the lab RTX 5060 Ti 16 GB with fp8
   weights and fp8 KV is enough; keep the app's limit at 8 to 16 requests at once. Hardware already owned; for a
   new server of this class, one card is about CA$1,000 to 1,300.
2. **A class of 200, or two or three courses sharing one server**: one RTX 5070 Ti 16 GB (about CA$1,100 to
   2,200, estimated about twice the lab card) or a second 5060 Ti as a second model connection. Measure before
   buying a second card.
3. **Renting instead of a lab server** (for example if the server must run in the university's AWS account):
   an L4 (`g6.xlarge`, about $154 a month for class hours) is enough only up to about 100 students; above that, a
   GPU with more bandwidth (L40S, RTX 4090 or 5090 class) is needed, which AWS offers only in larger, more
   expensive instances (not priced here).
4. **Design Day and the video**: the lab server through a tunnel (DEMO_VLLM.md) or a RunPod pod for the slot
   only. Demo data only.

## Sources

- Lab server: vLLM `/metrics` (`vllm:cache_config_info`) read on 2026-11-23; the GPU model from the lab owner.
- Load tests: `eval/load-test/app_load.py`, `eval/load-test/results/app_load_*`; the 2048-token research
  `eval/load-test/TOKEN_LIMIT_RESEARCH.md`; Z23 `eval/load-test/results/capacity.md`.
- Card specifications: [Tom's Hardware, RTX 5060 Ti 16GB review](https://www.tomshardware.com/pc-components/gpus/nvidia-geforce-rtx-5060-ti-16gb-review),
  [TechSpot, RTX 4060 Ti 16GB](https://www.techspot.com/specs/gpu/280961-nvidia-geforce-rtx-4060-ti-16gb.html),
  [TechSpot, RTX 5070 Ti](https://www.techspot.com/news/110227-nvidia-geforce-rtx-5070-ti-drops-729.html),
  [videocardbenchmark, 5060 Ti 16GB vs 5080](https://www.videocardbenchmark.net/compare/6160vs5721/GeForce-RTX-5060-Ti-16GB-vs-GeForce-RTX-5080),
  [NVIDIA L40S](https://www.nvidia.com/en-us/data-center/l40s/),
  [getdeploying, L40S vs RTX 5090](https://getdeploying.com/gpus/nvidia-l40s-vs-nvidia-rtx-5090),
  [gpuperhour GPU specs](https://gpuperhour.com/reference/gpu-specs).
- Card prices: [buygpu.ca](https://buygpu.ca/) (listings of 2026-11-21),
  [thedeskbrief GPU price tracker](https://thedeskbrief.com/gpu-price-tracker/),
  [tech-insider, RTX 5070 Ti Canada](https://tech-insider.org/ca/rtx-5070-ti-canada-price-2026/),
  [shattered.io, RTX 5090 list vs street](https://shattered.io/best-graphics-card-rtx-5090-1999-list-vs-6199-street-2026/),
  [PC Gamer, Black Friday GPU deals](https://www.pcgamer.com/black-friday-graphics-card-deals/).
- Rented GPUs: [RunPod pricing](https://www.runpod.io/pricing),
  [neroengine, RunPod pricing 2026](https://neroengine.com/runpod-pricing),
  [memetik, RunPod pricing September 2026](https://www.memetik.ai/guides/runpod-pricing),
  [diyai, RunPod pricing 2026](https://diyai.io/ai-tools/hosting/runpod-pricing/),
  [computeprices, RunPod](https://computeprices.com/providers/runpod),
  [doit, AWS g6.xlarge ca-central-1](https://www.doit.com/compute/spot/ca-central-1/g6.xlarge).
- Throughput of consumer cards for LLMs (for the bandwidth scaling):
  [hardware-corner, RTX 5060 Ti 16GB](https://www.hardware-corner.net/gpu-llm-benchmarks/rtx-5060-ti-16gb/),
  [modelfit, 5070 Ti vs 5080](https://modelfit.io/compare/rtx-5070-ti-vs-rtx-5080-llm/),
  [runaihome, consumer GPU inference 2026](https://runaihome.com/blog/realtime-llm-inference-consumer-gpu-2026/).
