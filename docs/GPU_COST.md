# Local model hosting cost (task V13, draft of 2026-11-19, for Prof. Abbas by 12/1)

PACT needs one GPU server for its local model (vLLM, Qwen3.5-9B): every question with personal data and every
learner-profile prompt goes there, never to a cloud model. Prof. Abbas set no fixed budget but asked for the
cost to be justified. Prices are USD, on-demand, checked on 2026-11-19 from public price lists and comparison
sites; check the providers' own pages before buying, prices change often.

**Capacity (Z23, lab vLLM, measured 2026-11-20, OPERATIONS.md section 10):** about 43 tokens/s for one answer,
up to about 475 tokens/s in total with short prompts and 120 to 160 tokens/s with course passages in the prompt.
One GPU of that class serves about 8 answers at the same time with p95 under 25 s, roughly 60 students working
at the same time (one question every 2 minutes, an assumption); a larger class needs a second GPU. The GPU model
of the lab server was not recorded, so the numbers do not yet say which rented GPU matches them: repeat
`eval/load-test/capacity.py` on the rented GPU before buying.

## What the model needs

Qwen3.5-9B in bf16 is about 18 GB of weights, so the GPU needs at least 24 GB (L4, RTX 4090, A5000/A10G or
larger) for a usable context (16k tokens). A 48 GB GPU (A40, L40S) allows more answers at the same time.

## Options

"Class hours" = 8 hours a day, 5 days a week (about 172 hours a month), the server started and stopped on a
schedule. "24/7" = 730 hours a month.

| Option | GPU | Price per hour | Class hours / month | 24/7 / month | Notes |
|---|---|---|---|---|---|
| RunPod Secure Cloud | L4 24 GB | $0.49 | ~$84 | ~$358 | cheapest; provider outside the university; data centre in Canada not guaranteed |
| RunPod Secure Cloud | RTX 4090 24 GB | $0.74 | ~$127 | ~$540 | faster than an L4 |
| RunPod Secure Cloud | A40 48 GB | $0.49 | ~$84 | ~$358 | more room for answers at the same time |
| RunPod Community Cloud | RTX 4090 | about $0.34 | ~$58 | ~$248 | hosts run by third parties: demo data only |
| AWS EC2 `g6.xlarge`, ca-central-1 | L4 24 GB | about $0.89 | ~$154 | ~$652 | same AWS account and Canadian region as the rest of PACT; a Savings Plan lowers 24/7 cost |
| AWS EC2 `g6.xlarge` spot, ca-central-1 | L4 24 GB | about $0.40 to $0.62 | ~$70 to $107 | not reliable | can be taken back at any time: not for class hours |
| Own server in the lab | one RTX 4090 or similar | hardware once (a workstation, roughly CA$4,000 to 5,000) plus power | — | — | the lab vLLM today; reachable from AWS only through a tunnel (DEMO_VLLM.md); depends on the lab's network and uptime |

Disk for the model and the image is extra but small (a 50 GB volume is a few dollars a month).

## Recommendation (to confirm with Prof. Abbas)

1. **Design Day and the video:** RunPod Secure Cloud (L4 or A40) only for the demo slots, or the lab server
   through a tunnel (DEMO_VLLM.md). Cost: a few dollars. Demo data only.
2. **A real course next term:** an AWS `g6.xlarge` in ca-central-1 in Prof. Abbas's account, started for class
   hours by a schedule: about $150 a month per GPU, everything in one Canadian AWS account (no third party
   receives student text). Move to 24/7 with a Savings Plan only if students use it outside class hours (the
   statistics of V2 show it).
3. Size the number of GPUs from the Z23 numbers and the expected active students; one GPU for the first course.

## Sources
- RunPod pricing: https://www.runpod.io/pricing and the September 2026 Secure Cloud change summarized at
  https://www.usagepricing.com/blueprint/activity/runpod-2026-09-20-secure-cloud-price-hike
- AWS `g6.xlarge` in ca-central-1: https://www.doit.com/compute/spot/ca-central-1/g6.xlarge (on-demand and spot)
