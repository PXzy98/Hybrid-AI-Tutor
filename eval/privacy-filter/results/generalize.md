# E6: hypothetical rewrite with the real local model

Local model `qwen3.5:9b`; the same prompt and checks as `app/privacy/generalize.py`. A rewrite that fails any check keeps the question local (the student still gets a local answer).

| Set | Personal-health questions | Rewrite sent to the cloud | Kept local | Identifiers left in a sent rewrite |
|---|---|---|---|---|
| main set | 61 | 60 (98%) | 1 | 0 |
| held-out v2 | 80 | 69 (86%) | 11 | 0 |

Why rewrites were kept local: filter finding 8, first person 3, grade 1.

## Examples (first 12 of held-out v2)

| Question | Rewrite | Outcome |
|---|---|---|
| Professor, I'm Isabella Rossi. I got this really bad migraine last week, can you explain t | Professor, for a person who experiences a severe migraine, could you explain the trigeminal nerve pathway? | sent |
| Liam Chen here. Help me with the BP readings. I measured 14/90 this morning. Is that conce | Is a blood pressure reading of very high systolic and very high diastolic values concerning? | sent |
| My name is Sofia Rodriguez, and I'm struggling with Pneumonia symptoms. Can you clarify th | What is the inflammatory response in a person struggling with pneumonia symptoms? | sent |
| My name is Wei Lin. I had terrible head pain this week. Is chronic migraine always genetic | Is a person who experiences severe headaches always genetically predisposed to developing chronic migraines? | sent |
| Professor, I think my wife might have some pneumonia. What's the worst-case scenario for a | Professor, what is the worst-case scenario for an elderly person with suspected pneumonia? | sent |
| Hey, has Michael Rodriguez been diagnosed with severe asthma? My classmate Ben Cho was ask | Has a person with severe asthma been diagnosed, and how do inhalers work for treating this condition? | sent |
| I'm panicking trying to find the treatment options for pneumonia! My friend Omar Kazi said | What are the short-term recovery protocols for a person with pneumonia? | sent |
| Did anyone see the assignment about migraine triggers? My classmate, Sofia Mendoza, mentio | Did anyone see the assignment about migraine triggers, and is there a mention of a person who experienced a se | sent |
| My phone kept ringing, and Jessica Lin told me she has serious breathing issues. I'm worri | For a person with serious breathing issues such as asthma, can you elaborate on the preventative strategies di | sent |
| What are the long-term effects of consistently high blood pressure? Marcus Chen says his u | What are the long-term effects of consistently high blood pressure, and do textbooks require citations for hyp | sent |
| My sister, Liliana Santos, told me she has pneumonia and needs to adjust her routine. Is t | Is the recuperation period for a person with pneumonia usually three to four weeks or longer, and how do the a | sent |
| I tried to email David Petrov about treatment side effects, but couldn't. His migraine med | Does the course cover dosage titration for severe headache disorders when a patient experiences trouble with t | filter finding: HEALTH_DETAIL |
