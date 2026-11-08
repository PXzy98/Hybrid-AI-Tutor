# Privacy profiles (task Z7)

Each course type has a privacy profile: one YAML file in `backend/app/privacy/profiles/`. The course's
`course_type` (course row, or the course setting of the same name) selects it; the privacy filter then runs the
profile's recognizers, and the generate step uses its health-detail policy.

| File | Contents |
|---|---|
| `base.yaml` | the layer of every course: student IDs, grades, names in context, Chinese and French names and grades, phone numbers, contacts, addresses, postal codes, dates of birth, ID and health-card numbers, credentials (`secret_token`: API keys, tokens, private keys, assigned passwords; Z11), and the light personal-health detector (`health_detail`); policy `local_only` |
| `medical_science.yaml` | base + `health_context`, `health_extra`, `fr_health`; policy `generalize`; checker `medical_safety`; "not medical advice" notice (the v3 behaviour) |
| `ece.yaml` | base + `internal_address` (private IPv4 host addresses with a port, MAC addresses; a network like `10.0.0.0/8` is kept) and `repo_url` (code-host URLs that name an account); test set `eval/privacy-filter/ece_cases.jsonl`, results `eval/privacy-filter/results/ece/` (Z11) |
| `life_science.yaml`, `general.yaml` | the base layer |

Format:

```yaml
extends: base                 # every profile builds on the base layer
recognizers: [health_context] # added to the base layer's (names from app/privacy/recognizers)
health_detail_policy: generalize   # local_only | generalize
checkers: [medical_safety]
medical_disclaimer: true
consent_note: >-            # added to the onboarding consent text of this course type (Z11)
  ...
```

**A new course type needs one file**: it then appears as a course type (settings and course creation). Files are
validated when loaded; an unknown recognizer, checker or key stops the app.

**Rules**: Presidio's own recognizers (names, e-mail addresses, phone numbers, ...) always run. The health-detail
policy is the stricter of the profile and `privacy.health_detail_policy` in `config.yaml` (`local_only` wins).
An explicit `privacy.recognizers` list in `config.yaml` (the E6 ablation) applies to every course instead of the
profiles. Any change to a profile's recognizers re-runs E6 (rule 5).

## Document scanning, web search queries, consent text (task Z11)

- `scan_document(text, profile)` runs the profile's analyzer over an uploaded document (in windows of 20,000
  characters that overlap by 4,000, so a value at a window edge is also seen whole; overlapping findings of a
  type count once) and returns entity types and counts, never the matched text.
  `ScanResult.blocking` lists the found types that are student data (`BLOCKING_TYPES`: student IDs, grades,
  ID and health-card numbers, dates of birth, credentials, personal health details). Names, e-mail addresses
  and phone numbers are reported but do not block, because course documents name their staff and authors.
- `search_query(ctx)` is the only source of web search queries (guide rule 5). It reads only the privacy
  filter's sanitized text, returns None for a local-only question, drops every sentence that held personal
  data (a placeholder) and returns None when fewer than three words are left; at most 200 characters.
- `consent_text(profile)` is the onboarding consent text: the reviewed base text plus the profile's
  `consent_note` (medical and ECE have one).
