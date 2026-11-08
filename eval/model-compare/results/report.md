# Z2: Qwen3.5 9B vs 27B (both with RAG)

84 check items, 20 open questions. Models through OpenRouter (qwen/qwen3.5-9b, qwen/qwen3.5-27b), temperature 0, thinking off; judge anthropic/claude-sonnet-5.5 (another family), blind and in random order. Total cost of the cached calls: $0.10.

## 1. Check items (multiple choice, answer key)

| Model | Without RAG | With RAG | basic | intermediate | advanced | Median s per answer |
|---|---|---|---|---|---|---|
| 9b | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.36 |
| 27b | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.58 |

**Ceiling effect**: both models answer (almost) every item correctly, even without RAG. These items do not separate the models; the open questions below do.

Answers without a readable letter count as wrong: 0.

Items both models get wrong with RAG: none.

## 2. Open questions with RAG (pairwise, judged)

| 9B better | 27B better | Tie | Unparsed |
|---|---|---|---|
| 4 | 10 | 6 | 0 |

| Question | Winner | Judge's reason |
|---|---|---|
| What do systolic and diastolic blood pressure mean? | 27b | Both answers define systolic and diastolic pressure accurately using the passages, but B stays focused on the question, while A adds extra material about regular checks and Stage 1 hypertension and states that the two numbers give a 'complete picture,' which the passages do not say. |
| How is high blood pressure diagnosed over multiple visits? | 9b | Answer B stays within the passages and accurately lists the blood pressure categories and thresholds, while Answer A adds unsupported claims (readings 'distinguishing between temporary spikes', diagnosis confirmed by Hypertensive Crisis readings across visits, 'a diagnosis is not made after a single |
| What changes can help manage hypertension? | tie | Both answers accurately reflect the passages, covering lifestyle changes, medication if needed, treating underlying causes, and working with a provider, and neither adds unsupported claims. |
| Why is high blood pressure dangerous over time? | 27b | Both answers correctly state that sustained high pressure makes the heart work harder and can cause heart attack, stroke, heart failure, and kidney failure, but A stays focused on the question while B adds tangential material on types and hypertensive crisis thresholds that does not explain why it i |
| What common allergens may trigger allergic asthma? | 27b | Answer A lists all five allergens from the passage accurately, including pets, while Answer B omits pets from its list of examples, which makes it less complete, and it adds nonallergic triggers that the question did not ask about. |
| What are typical symptoms of asthma? | 9b | Both list the symptoms correctly, but B draws on more of the passages (attacks coming on gradually or suddenly, emergency care when quick-relief medicines fail) and stays accurate, while A's "if not managed properly" is not in the passages. |
| How does a clinician test lung function for asthma? | tie | Both answers accurately describe spirometry, the challenge test, PEF and FeNO as given in the passages, with only minor differences in framing and formatting. |
| When does a severe asthma attack require emergency care? | tie | Both correctly state that emergency care is needed when quick-relief medicines do not work, and both add that attacks can be life-threatening, particularly in severe asthma, drawing accurately on the passages with similar clarity. |
| What are some environmental triggers for migraines? | 9b | Both answers correctly list lights, noises, smells, and weather changes, but B stays closer to environmental triggers (adding tobacco as a borderline case) and notes that triggers vary and a log helps, while A pads with lifestyle and food triggers that are not environmental, though it does flag them |
| How can you feel in the postdrome after a migraine? | tie | Both answers correctly say the postdrome brings exhaustion, weakness, and confusion for up to a day, and both add the same minor embellishment ('mental fog'); B also lists the four phases, but that adds little. |
| What symptoms can accompany migraine attacks? | 27b | Both answers are accurate and use the passages, but A is more complete on the phases: it includes fluid retention in the prodrome, notes that migraines can occur without a headache, and says not everyone goes through every phase. B omits those points and adds timing details that don't answer the que |
| What can help during a migraine attack without medicine? | 27b | The passages cover prevention rather than relief during an attack, and Answer B says so explicitly, while Answer A presents symptom descriptions and worsening factors as if they were strategies for managing an attack, which is misleading. |
| Which kinds of infection can cause pneumonia? | 27b | Both answers are correct on bacterial, viral, and fungal causes, but B also draws on the passage's fungal examples (histoplasmosis, cryptococcal pneumonia), so it uses the passages more fully, and it is concise; A calls aspiration a 'direct infectious cause' framing that is slightly muddled. |
| What breathing symptoms can pneumonia cause? | 27b | Both list the core breathing symptoms accurately, but A stays closer to the passages, while B adds unsupported details (the respiratory failure definition) and drifts into diagnosis; A's claim about milder breathing symptoms in older adults is a minor stretch, though B's 'newborns might not show obv |
| What is bacteremia, a complication of pneumonia? | 27b | Both answers define bacteremia correctly, but A stays focused on the question, while B adds loosely related details about causes and viral precursors that do not explain bacteremia. |
| What would a doctor listen to during a pneumonia exam? | 27b | Both correctly say the provider listens to the lungs with a stethoscope, but A stays within the passages, while B claims the stethoscope sound helps assess severity and determine treatment, which the passages don't support, and adds unneeded treatment detail. |
| What test measures average blood glucose over three months? | tie | Both answers correctly identify the A1C test and accurately contrast it with the FPG and RPG tests, which measure current glucose, using the passage; they are equally clear and differ only in minor wording. |
| What are early signs of type 2 diabetes? | tie | Both answers accurately report from the passages that many people have no symptoms, that symptoms develop slowly and can be mild, and they list the same symptoms; both add a screening recommendation for higher-risk people, and the differences are only in formatting. |
| How does family history affect type 2 diabetes risk? | 9b | Both answers correctly say family history raises risk, but B notes that the passages do not detail the mechanism, while A states a genetic link to insulin resistance as if the text supports it; B also adds relevant preventive steps from the passages. |
| Does prediabetes increase the risk of type 2 diabetes? | 27b | Both answers correctly say yes and cite the passage, but A also gives the specific prevention steps (weight loss, fewer calories, more activity), while B adds the unsupported word "significantly" and only vaguely says that managing conditions lowers risk. |

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
