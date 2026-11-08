# Z2: Qwen3.5 9B vs 27B (both with RAG)

84 check items, 20 open questions. Models through OpenRouter (qwen/qwen3.5-9b, qwen/qwen3.5-27b), temperature 0, thinking off; judge anthropic/claude-sonnet-5.5 (another family), blind, each pair judged in both orders (a win only when both agree). Total cost of the cached calls: $0.16.

## 1. Check items (multiple choice, answer key)

| Model | Without RAG | With RAG | basic | intermediate | advanced | Median s per answer |
|---|---|---|---|---|---|---|
| 9b | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.34 |
| 27b | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.39 |

**Ceiling effect**: both models answer (almost) every item correctly, even without RAG. These items do not separate the models; the open questions below do.

Answers without a readable letter count as wrong: 0.

Items both models get wrong with RAG: none.

## 2. Open questions with RAG (pairwise, judged)

| 9B better | 27B better | Tie | Unparsed |
|---|---|---|---|
| 2 | 6 | 12 | 0 |

| Question | Winner | Judge's reason |
|---|---|---|
| What do systolic and diastolic blood pressure mean? | 27b | Both answers define systolic and diastolic pressure correctly and use the 120/80 example from the passages, but B stays focused on the question while A adds a slightly overstated claim that the two numbers 'provide a complete picture' of blood pressure status. |
| How is high blood pressure diagnosed over multiple visits? | tie | Both answers are accurate and grounded in the passages, but B better addresses the multi-visit question and ties the diagnostic thresholds to those visits, while A adds an inaccurate hypertensive-crisis detail ('180+/120+', where the passage says higher than 180 and/or higher than 120). |
| What changes can help manage hypertension? | tie | Both answers accurately reflect the passages: lifestyle changes (heart-healthy eating, exercise), medication if needed, possibly more than one type, treating underlying causes, and working with a provider. Neither adds unsupported claims, and both are equally clear. |
| Why is high blood pressure dangerous over time? | 27b | Both answers are correct and use the key passage, but B stays focused on why sustained high blood pressure is dangerous, while A adds tangential material on types and hypertensive crisis and claims 'regardless of the type' damage occurs, which the passages don't state. |
| What common allergens may trigger allergic asthma? | 27b | Answer B lists all five allergens from the passage, including pets, while Answer A omits pets and so gives an incomplete answer, though A's added diagnostic detail is accurate. |
| What are typical symptoms of asthma? | tie | Both answers list the four symptoms correctly, but B stays closer to the question and the passages. A adds emergency-care and treatment details that were not asked for, and B's 'if not managed properly' is a small embellishment but minor. |
| How does a clinician test lung function for asthma? | tie | Both answers are accurate and use the passages, but B states the spirometry-before-and-after-challenge point more precisely, mentions the physical exam and medical history, and is clearer to read with its bulleted list. |
| When does a severe asthma attack require emergency care? | tie | Both correctly say emergency care is needed when quick-relief medicines do not work, but B stays closer to the passages, while A adds the unsupported claim that symptoms 'cannot be controlled with your standard treatment plan' and blurs the passage's wording. |
| What are some environmental triggers for migraines? | tie | Both correctly list lights, noises, smells, and weather changes, but A calls tobacco use an environmental factor, which is questionable, while B correctly separates it as a lifestyle trigger and covers the other passage triggers (caffeine, skipped meals, foods) accurately. |
| How can you feel in the postdrome after a migraine? | tie | Both correctly give exhausted, weak, and confused, lasting up to a day, but B stays closer to the passages, while A adds the unsupported claim that the postdrome follows 'the headache and potentially the aura', and B's 'mental fog' is only a mild paraphrase of 'confused'. |
| What symptoms can accompany migraine attacks? | tie | Both answers are accurate and use the passages, but B includes more of the passage details (fluid retention, migraine without headache, being touched) and is organized more clearly, while A adds the morning and timing information but omits those details. |
| What can help during a migraine attack without medicine? | 27b | The passages cover prevention rather than treatment during an attack, and B acknowledges this, while A stretches the passages by suggesting that avoiding movement relieves pain and that trigger-avoidance helps during an attack, neither of which the text states. |
| Which kinds of infection can cause pneumonia? | 9b | Both answers are accurate and use the passages well, but A states that bacterial pneumonia can occur independently or after a cold or flu, and it labels aspiration as a non-infectious cause that can lead to infection, which fits the passage better than B's brief note that viral infections can preced |
| What breathing symptoms can pneumonia cause? | tie | Both correctly list cough with phlegm, shortness of breath, and chest pain when breathing, but B stays focused on the question and its extras are mostly accurate, while A adds off-topic diagnosis details and claims 'breathing difficulties can still occur' for older adults, which the passages do not  |
| What is bacteremia, a complication of pneumonia? | 27b | Both answers define bacteremia correctly, but B stays focused on the question and ties it to hospital treatment, while A adds loosely relevant detail about treatment and a prevention claim the passages do not support. |
| What would a doctor listen to during a pneumonia exam? | 27b | Both correctly say the doctor listens to the lungs with a stethoscope, but B stays closer to the question and explains that fluid in the air sacs causes abnormal sounds; A adds treatment details that are off-topic and says the sounds determine the treatment, which the passages do not support. |
| What test measures average blood glucose over three months? | tie | Both correctly identify the A1C test as measuring average blood glucose over 3 months and accurately contrast it with the FPG and RPG tests, using the passage in the same way and with similar clarity. |
| What are early signs of type 2 diabetes? | tie | Both answers correctly list the passage's symptoms, but B stays closer to the passages and notes that high-risk people should be vigilant even if they feel fine, which fits the point that many people have no symptoms. A adds an unsupported claim that early detection helps manage the condition and th |
| How does family history affect type 2 diabetes risk? | 9b | Answer A stays within the passages and explicitly notes that the exact mechanism isn't detailed, while Answer B makes unsupported claims, such as that risk rises even without other risk factors and that genetics makes the body more susceptible to obesity and inactivity issues. |
| Does prediabetes increase the risk of type 2 diabetes? | tie | Both answers correctly say yes and cite the passage, but B is more faithful to it, since it links prediabetes to the specific prevention steps (weight loss, fewer calories, more activity). A adds 'significantly,' which the passage does not support, and its prevention link is vaguer. |

## 3. vLLM memory estimate (not measured)

Weights from the parameter count; KV cache 2 × full-attention layers × KV heads × head size × 2 bytes per token, from the models' config.json (only every fourth layer is full attention; the fixed state of the linear-attention layers is left out). An estimate to plan with, not a measurement.

| Model | Weights BF16 | Weights 4-bit (AWQ/GPTQ) | KV cache per 8k-token request (FP16) | Fits on one 24 GB GPU with 4 parallel 8k requests | 48 GB |
|---|---|---|---|---|---|
| 9b | 18 GiB | 5.0 GiB | 0.25 GiB | yes (8.0 GiB) | yes |
| 27b | 54 GiB | 15.1 GiB | 0.50 GiB | yes (19.1 GiB) | yes |

## Limits

- Hosted inference, not the course server: quality is comparable, latency and throughput are not (run eval/load-test on the server).
- The check items are the unreviewed draft bank of the demo course; a wrong answer key counts against both models alike.
- One judge model; 20 open questions give a wide margin of error.
