# E3: personalization on vs off (design §11 E3)

4 personas × 20 questions × on/off = 160 answers · judge `gemma4:e4b`, blind, random A/B order · 80 of 80 pairs judged.

| Metric | Personalized | Not personalized | Target (ideal / marginal) | Verdict |
|---|---|---|---|---|
| Win rate, "level fits this student" (ties = ½) | 85% | — | ≥ 65% / 55% | ✅ ideal |
| Correct answers | 98% | 100% | no drop | ❌ |
| Critical errors | 0 | 0 | no rise | ✅ |
| Known misconception addressed | 100% | 75% | ≥ 80% / 70% | ✅ ideal |
| Preference respected | 90% | — | ≥ 90% | ✅ ideal |

**Decision (design §11 E3):** keep personalization as designed (level, misconception note, preference templates).

**Correctness criterion not met** ("no drop in correctness or rise in critical errors"). Review these personalized answers before relying on the decision above:

- intermediate_mc Q05: judged `minor_error` — I can't give a safe general answer to this question here. Questions about your own health, medicines or doses need a doctor, nurse or pharmacist, who can look a…
- mixed Q05: judged `minor_error` — Doctors usually decide if someone has high blood pressure by taking a reading with a cuff on the arm and checking it over time, since one single number can be m…

## By persona

| Persona | Pairs | Personalized wins | Ties |
|---|---|---|---|
| novice | 20 | 20 | 0 |
| intermediate_mc | 20 | 19 | 0 |
| advanced | 20 | 20 | 0 |
| mixed | 20 | 9 | 0 |

Judge failures: 0.
Dr. Abbas sample: `abbas_sample.csv` (30 pairs, blind); key in `abbas_key.csv`.
