# Privacy profiles (task Z7)

Each course type has a privacy profile: one YAML file in `backend/app/privacy/profiles/`. The course's
`course_type` (course row, or the course setting of the same name) selects it; the privacy filter then runs the
profile's recognizers, and the generate step uses its health-detail policy.

| File | Contents |
|---|---|
| `base.yaml` | the layer of every course: student IDs, grades, names in context, Chinese and French names and grades, phone numbers, contacts, addresses, postal codes, dates of birth, ID and health-card numbers, and the light personal-health detector (`health_detail`); policy `local_only` |
| `medical_science.yaml` | base + `health_context`, `health_extra`, `fr_health`; policy `generalize`; checker `medical_safety`; "not medical advice" notice (the v3 behaviour) |
| `life_science.yaml`, `ece.yaml`, `general.yaml` | the base layer; their own recognizers and test sets come with task Z11 |

Format:

```yaml
extends: base                 # every profile builds on the base layer
recognizers: [health_context] # added to the base layer's (names from app/privacy/recognizers)
health_detail_policy: generalize   # local_only | generalize
checkers: [medical_safety]
medical_disclaimer: true
```

**A new course type needs one file**: it then appears as a course type (settings and course creation). Files are
validated when loaded; an unknown recognizer, checker or key stops the app.

**Rules**: Presidio's own recognizers (names, e-mail addresses, phone numbers, ...) always run. The health-detail
policy is the stricter of the profile and `privacy.health_detail_policy` in `config.yaml` (`local_only` wins).
An explicit `privacy.recognizers` list in `config.yaml` (the E6 ablation) applies to every course instead of the
profiles. Any change to a profile's recognizers re-runs E6 (rule 5).
