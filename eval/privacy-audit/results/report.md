# E4: privacy audit of cloud requests (design §11 E4)

4 personas × 70 questions = 280 asks, all forced to the cloud route; provider: local echo (nothing left the machine).

Targets: fields outside the allow-list: 0 · profile or identity leak: 0 · PII leak ≤ 1% ideal / 5% marginal.

| Result | Value |
|---|---|
| Cloud requests recorded | 260 (from 260 asks) |
| Asks kept local (not cloud-safe, or blocked by the pre-send guard) | 20 (guard warnings: 0) |
| Fields outside the allow-list | 0 |
| Identity leaks | 0 |
| Profile leaks | 0 |
| PII leaks in cloud requests | 0 (0.0% of requests) |
| Typed PII or identity stored in the DB or logs | 0 |

## Findings

- none

## Asks kept local

- novice: My reading was high once at the pharmacy, so that means I have high blood pressure, right?
- novice: My blood pressure is normal now, so I can stop my medication, right?
- novice: I only take my pills on days when I feel bad, that's fine isn't it?
- novice: I have asthma and high blood pressure. Is regular exercise a good idea in general?
- novice: My mother, Ana Ferreira, takes two blood pressure pills. Why would a doctor prescribe two?
- intermediate_mc: My reading was high once at the pharmacy, so that means I have high blood pressure, right?
- intermediate_mc: My blood pressure is normal now, so I can stop my medication, right?
- intermediate_mc: I only take my pills on days when I feel bad, that's fine isn't it?
- intermediate_mc: I have asthma and high blood pressure. Is regular exercise a good idea in general?
- intermediate_mc: My mother, Ana Ferreira, takes two blood pressure pills. Why would a doctor prescribe two?
- advanced: My reading was high once at the pharmacy, so that means I have high blood pressure, right?
- advanced: My blood pressure is normal now, so I can stop my medication, right?
- advanced: I only take my pills on days when I feel bad, that's fine isn't it?
- advanced: I have asthma and high blood pressure. Is regular exercise a good idea in general?
- advanced: My mother, Ana Ferreira, takes two blood pressure pills. Why would a doctor prescribe two?
- mixed: My reading was high once at the pharmacy, so that means I have high blood pressure, right?
- mixed: My blood pressure is normal now, so I can stop my medication, right?
- mixed: I only take my pills on days when I feel bad, that's fine isn't it?
- mixed: I have asthma and high blood pressure. Is regular exercise a good idea in general?
- mixed: My mother, Ana Ferreira, takes two blood pressure pills. Why would a doctor prescribe two?

**Verdict: no leak**
