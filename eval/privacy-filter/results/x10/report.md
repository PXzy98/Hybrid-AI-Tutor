# X10: the biomedical engineering held-out set

Set: `bme_holdout.jsonl` (make_bme_set.py), 95 fictional messages (75 with personal data, 20 without):
written by Claude Haiku 5.5 and GPT-6 Luna through OpenRouter from the course subject only, labelled by
Claude Sonnet 5.5 and GPT-6.1 Terra. 80 rows both labellers agreed on; 15 decided by Z on 2026-11-25 (the
shorter core span counts; the four other decisions are in the script; one row dropped). Scored by
`course_sets.py` with the rules only (no local model check, no generalize rewrite): an entity counts as
protected when 80% of its characters are found.

| Profile | Leak (messages with an entity not protected) | Over-redaction (clean messages with a finding) | Keep terms lost |
|---|---|---|---|
| `general` | 68.0% | 10.0% | 3 |
| `medical_science` | 68.0% | 25.0% | 8 |
| `ece` | 58.7% | 10.0% | 3 |
| `biomedical_engineering` | 58.7% | 25.0% | 8 |

Recall by type with `biomedical_engineering`: student number, e-mail, lab address 100%; phone 95%; name 87%;
secret 32%; grade 29%; address 25%; health detail 23%; repository URL 0%.

The other course sets are unchanged (ECE 4.0%, computer science 0.0%, life science 13.3%, general 0.0% leak,
as after Z22b): adding a profile changes no other profile.

## What the rules miss (to fix in a follow-up task, E6 before and after)

- **Health details of the student or a relative** (24 misses): own wearable or lab readings ("resting heart
  rate of 104 bpm", "my pulse on the PPG read like 58"), a relative's condition and medicine ("paroxysmal
  AFib", "apixaban"), devices ("I've got a pacemaker"). The local model's check (`privacy.llm_check`, on by
  default) runs for such questions in the app; this table measures the rules alone.
- **Bare keys and tokens** (15): `sk_notreal_...`, `FAKE-KEY-...` without an assignment like `key =`.
- **Grades without a grade word** (5): "got a 71 on the ECG filter quiz", "came back as a B-".
- **Repository URLs on other hosts** (3): `https://git.example.org/<account>/<repo>`.
- **Over-redaction**: "my ECG trace", "my ECG signal" in lab questions are taken as the student's own health
  reading (`health_extra`), so such questions stay on the local model and lose the term.
