# Privacy profiles (task Z7)

Each course type has a privacy profile: one YAML file in `backend/app/privacy/profiles/`. The course's
`course_type` (course row, or the course setting of the same name) selects it; the privacy filter then runs the
profile's recognizers, the generate step uses its health-detail policy, the prompt uses its subject prompt and
the verify step runs its checkers (task Z16).

| File | Contents |
|---|---|
| `base.yaml` | the layer of every course: student IDs, grades, names in context, Chinese and French names and grades, phone numbers, contacts, addresses, postal codes, dates of birth, ID and health-card numbers, credentials (`secret_token`: API keys, tokens, private keys, assigned passwords; Z11; since Z22b also prefixed names such as `AWS_SECRET_ACCESS_KEY=`, `Bearer` tokens, URL passwords and "the password for X is V"), and the light personal-health detector (`health_detail`); policy `local_only` |
| `medical_science.yaml` | base + `health_context`, `health_extra`, `fr_health`; policy `generalize`; checker `medical_safety`; "not medical advice" notice; subject prompt `health` (the v3 behaviour) |
| `ece.yaml` | subject prompt `engineering`; base + `internal_address` (private IPv4 host addresses with a port, MAC addresses; a network like `10.0.0.0/8` is kept) and `repo_url` (code-host URLs that name an account, also `git@host:account/repo`; Z22b); test set `eval/privacy-filter/ece_cases.jsonl`, results `eval/privacy-filter/results/ece/` (Z11) |
| `life_science.yaml`, `general.yaml` | the base layer; subject prompt `general` |

Format:

```yaml
extends: base                 # every profile builds on the base layer
recognizers: [health_context] # added to the base layer's (names from app/privacy/recognizers)
health_detail_policy: generalize   # local_only | generalize
checkers: [medical_safety]
medical_disclaimer: true
prompt: health                # subject prompt: backend/app/prompts/subjects/<prompt>.md (default general)
consent_note: >-            # added to the onboarding consent text of this course type (Z11)
  ...
```

**Subject prompt and checkers (task Z16)**: the system prompt is `prompts/base_system.md` (the rules of every
course: cite the material, invent nothing, no diagnosis or personal medical advice, emergencies) followed by
`prompts/subjects/<prompt>.md`. Only `health` makes the tutor a health-education tutor with the rules on
medicines and doses. A checker that some profile lists (today `medical_safety`) belongs to that subject: the
verify step runs it only for courses whose profile lists it, so a lab answer in an ECE course ("inject 5 ml of
the sample") is not replaced by the medical fallback. `medical_disclaimer` is read by nothing yet.

**A new course type needs one file**: it then appears as a course type (settings and course creation). Files are
validated when loaded; an unknown recognizer, checker or key stops the app.

**Rules**: Presidio's own recognizers (names, e-mail addresses, phone numbers, ...) always run. The health-detail
policy is the stricter of the profile and `privacy.health_detail_policy` in `config.yaml` (`local_only` wins).
An explicit `privacy.recognizers` list in `config.yaml` (the E6 ablation) applies to every course instead of the
profiles. Any change to a profile's recognizers re-runs E6 (rule 5).

## Personal health details the term list does not know (task Z22d, 2026-11-23)

Found while planning the video: "I have a perianal abscess and need to submit my assignment late" had no
finding in any profile, so it was cloud-safe (with a name and a student number the cloud would have received
"I'm <PERSON_1>, student number <STUDENT_ID_1>. I have a perianal abscess ..."). Two changes:

- **Rules** (`health_detail`, every profile): more conditions, still only when attributed to the student or a
  relative ("I have", "my brother has"): abscesses, words ending in -itis, named tumours (-oma: melanoma,
  lymphoma, ...; not "diploma"), cysts, ulcers, hernias, kidney stones, concussions, injuries, fractures and
  sprains of a body part ("fracture mechanics" is not one), infectious diseases (strep throat, shingles,
  measles, ...); "diagnosed with / treated for / hospitalized for <up to three words>" for a condition no list
  names; "I broke my wrist" style injuries. General questions ("How is an abscess treated?") stay cloud-safe.
- **The local model's second check** (`privacy.llm_check`, `app/privacy/llm_check.py`) is **on by default**
  (code default and `config.yaml`), because the deployment always has its trusted local model (Z24). It now
  reads a cloud-bound question that names a health topic **or** has a first-person wording that may carry a
  health detail the rules do not know (`policy.may_reveal_health`: "I have/got a(n) <word that is not a course
  noun>", "unwell", "medical", "appointment", a late or missed piece of work "because ..."). It still sees only
  the redacted text, runs once per request, and fails closed. Its prompt fits every course type (a course
  about any subject; a health detail given as the reason for late or missed work counts; a name or number next
  to a general health question does not make it personal) (no reachable local model: the question stays
  local). Ordinary course questions still skip it. The test suite turns it off in `tests/conftest.py` and on in
  its own tests.

E6 and the counts of questions the check reads: `eval/privacy-filter/results/z22d/report.md`.

## Document scanning, web search queries, consent text (task Z11)

- `scan_document(text, profile)` runs the profile's analyzer over an uploaded document (in windows of 20,000
  characters that overlap by 4,000, so a value at a window edge is also seen whole; overlapping findings of a
  type count once) and returns entity types and counts, never the matched text.
  `ScanResult.blocking` lists the found types that are student data (`BLOCKING_TYPES`: student IDs, grades,
  ID and health-card numbers, dates of birth, credentials, personal health details). Names, e-mail addresses
  and phone numbers are reported but do not block, because course documents name their staff and authors.
- **Grades and health details block only when they belong to someone the document identifies** (2026-11-12):
  a direct identifier (student ID, e-mail, phone, ID or health-card number, date of birth) within 300
  characters; for a grade, a name also counts ("Ann Lee got a B+"). Otherwise they are listed in
  `ScanResult.unattached`, reported but not blocking: course material is full of fictional patients ("a 29
  year old male ... believes he has diabetes") and worked examples. The rule applies to documents only; the
  question filter treats every finding as before. Found by scanning the open course packs
  (`data/demo_courses/`): 16 of 295 files were refused before, none after; tests in
  `backend/tests/test_scan_false_positives.py`.
- Recognizer fixes from the same scan (they apply to questions too; E6 re-run, not worse): an ISBN, a run of
  one repeated digit and digits split by more than one kind of separator ("30.0-34.9 25.0") are not student
  numbers; a placeholder ("token=API_KEY", "YOUR_PASSWORD", "<your-api-key>") is not a credential; an A or B
  inherited from a parent is not a grade; "induction", "injection" and similar words are not misspellings of
  "infection".
- `search_query(ctx)` is the only source of web search queries (guide rule 5). It reads only the privacy
  filter's sanitized text, returns None for a local-only question, drops every sentence that held personal
  data (a placeholder) and returns None when fewer than three words are left; at most 200 characters.
- `consent_text(profile)` is the onboarding consent text: the reviewed base text plus the profile's
  `consent_note` (medical and ECE have one).
