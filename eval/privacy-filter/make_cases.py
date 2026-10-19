"""Generate the E6 privacy-filter test set (eval/privacy-filter/cases.jsonl). All data is fictional.

    .venv\\Scripts\\python eval\\privacy-filter\\make_cases.py

Templates combine fictional identities with carrier questions (`question_bank.json`, written by the local model
and reviewed by hand). Each case:
    {id, group, variant, text, entities: [{type, text}], personal_health, keep, self_name, conversation}
Groups:
- positive      in-scope PII written in common ways (must be found)
- negative      no personal information; nothing may be redacted, `keep` terms must survive
- hard          in-scope PII written in unusual ways (lower case, pinyin, spaced digits, typos, obfuscation)
- french        in-scope PII in French sentences (uOttawa is bilingual)
- multiturn     several messages of one conversation; each message is filtered on its own
- out_of_scope  personal data types the filter does not claim to cover (reported as gaps)
`personal_health` = a personal health detail is present (expected: not cloud-safe).
`self_name` = the asking student's own display name (the app adds it as an identity term).
"""
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
rng = random.Random(6)
BANK = [q for qs in json.loads((HERE / "question_bank.json").read_text("utf-8")).values() for q in qs]
BANK += ["What does the bottom number in a blood pressure reading mean?", "Why does salt raise blood pressure?",
         "How is high blood pressure diagnosed?", "What is the DASH diet?", "How does insulin work?",
         "What triggers an asthma attack?", "What is the difference between a migraine and a headache?"]

NAMES = ["Lucas Bergeron", "Maya Okafor", "Priya Raman", "Tom Nguyen", "Aisha Mohammed", "Wei Zhang",
         "Sofia Rossi", "Kwame Mensah", "Olivia Brown", "Mateo Garcia", "Hiroshi Tanaka", "Fatima Zahra",
         "Daniel Kowalski", "Ana Ferreira", "Arjun Patel", "Emily Chen", "Noah Tremblay", "Grace Lee",
         "Omar Haddad", "Isabelle Roy", "Siobhan O'Connor", "Jose Alvarez", "Ngozi Adeyemi", "Liam Murphy",
         "Yuki Sato", "Elena Petrova", "Samir Khan", "Chloe Gagnon", "Marcus Johnson", "Leila Hosseini"]
PINYIN = ["Zhang Wei", "Li Mingxuan", "Wang Fang", "Chen Jie", "Liu Yang"]
cases: list[dict] = []


def add(group, variant, text, entities=(), personal_health=False, keep=(), self_name=None, conversation=None):
    for t, s in entities:
        assert s in text, (text, s)
    for k in keep:
        assert k in text, (text, k)
    cases.append({"id": f"P{len(cases) + 1:03d}", "group": group, "variant": variant, "text": text,
                  "entities": [{"type": t, "text": s} for t, s in entities], "personal_health": personal_health,
                  "keep": list(keep), "self_name": self_name, "conversation": conversation})


def q():
    return rng.choice(BANK)


def ql():
    s = q()
    return s[0].lower() + s[1:]


def sid():
    return "300" + "".join(rng.choice("0123456789") for _ in range(6))


# =============================================================== positive
# PERSON: own name (6 forms) and other people's names (4 forms)
OWN = ["Hi, I'm {n}. {q}", "My name is {n} and I wonder: {q}", "This is {n} from section B. {q}",
       "{n} here, quick question. {q}", "Hello, {n} speaking. {q}", "Good morning, I am {n}. {q}"]
OTHER = ["My friend {n} asked me this: {q}", "My roommate {n} wants to know: {q}",
         "My study partner {n} and I disagree. {q}", "I was talking with {n} yesterday. {q}"]
for i, n in enumerate(NAMES):
    add("positive", "own_name", OWN[i % len(OWN)].format(n=n, q=q()), [("PERSON", n)], self_name=n)
for i, n in enumerate(NAMES[:20]):
    add("positive", "other_name", OTHER[i % len(OTHER)].format(n=n, q=q()), [("PERSON", n)])
for title, n in [("Ms.", "Grace Lee"), ("Mr.", "Omar Haddad"), ("Dr.", "Sarah Lindqvist"), ("Prof.", "Ian McLeod"),
                 ("Mrs.", "Ana Ferreira"), ("Dr.", "Hiroshi Tanaka")]:
    add("positive", "titled_other_name", f"{title} {n} told us something different. {q()}", [("PERSON", n)])

# STUDENT_ID
ID_FORMS = [("plain_context", "My student number is {s}. {q}"), ("plain_context", "Student ID {s} here. {q}"),
            ("plain_end", "{q} (student {s})"), ("plain_context", "For the record my id is {s}. {q}"),
            ("plain_no_context", "{s} — {q}"), ("hash", "ID #{s}: {q}"), ("colon", "student no.:{s} {q}")]
for i in range(28):
    variant, form = ID_FORMS[i % len(ID_FORMS)]
    s = sid()
    add("positive", f"id_{variant}", form.format(s=s, q=q()), [("STUDENT_ID", s)])
for i in range(4):
    s = sid()
    dashed = f"{s[:3]}-{s[3:6]}-{s[6:]}"
    add("positive", "id_dashed_context", f"My student number is {dashed}. {q()}", [("STUDENT_ID", dashed)])
    spaced = f"{s[:3]} {s[3:6]} {s[6:]}"
    add("positive", "id_spaced_context", f"Student ID: {spaced}. {q()}", [("STUDENT_ID", spaced)])

# EMAIL_ADDRESS
for i in range(20):
    first, last = rng.choice(NAMES).lower().replace("'", "").split(" ", 1)
    mail = [f"{first}.{last}@uottawa.ca", f"{first}{rng.randrange(10, 99)}@gmail.com", f"{last[:5]}{first[0]}@outlook.com",
            f"{first}_{last}@hotmail.com", f"{first[0]}{last}@cmail.carleton.ca"][i % 5]
    form = ["Please email the answer to {m}. {q}", "My email is {m}, {ql}", "{q} Reply to {m} please."][i % 3]
    add("positive", "email", form.format(m=mail, q=q(), ql=ql()), [("EMAIL_ADDRESS", mail)])

# PHONE_NUMBER
PHONES = ["613-555-0142", "(343) 555-0199", "+1 613 555 0123", "613.555.0188", "819-555-0101", "(613) 555-0177",
          "+1 (343) 555-0110", "613 555 0164", "1-613-555-0190", "416-555-0133"]
for i, ph in enumerate(PHONES * 2):
    form = ["You can call me at {p} if needed. {q}", "My cell is {p}. {q}", "Text me at {p}: {ql}"][i % 3]
    add("positive", "phone", form.format(p=ph, q=q(), ql=ql()), [("PHONE_NUMBER", ph)])

# GRADE
GRADES = [("I got 58/100 on the midterm. {q}", "I got 58/100"), ("I only got 62% on the quiz, so {ql}", "I only got 62%"),
          ("My GPA is 2.9 and I am worried. {q}", "My GPA is 2.9"), ("I failed the midterm last week. {q}", "I failed the midterm"),
          ("I scored 71 percent on the lab. {q}", "I scored 71 percent"), ("My grade dropped to 64 after the exam. {q}", "My grade dropped to 64"),
          ("I received a C+ on my assignment. {q}", "I received a C+"), ("My average is 78% right now. {q}", "My average is 78%"),
          ("I got a B- in the course. {q}", "I got a B-"), ("My mark on quiz 2 was 13/20. {q}", "My mark on quiz 2 was 13/20"),
          ("I earned 88 percent on the final. {q}", "I earned 88 percent"), ("My cgpa is 3.4. {q}", "My cgpa is 3.4"),
          ("I flunked the quiz. {q}", "I flunked the quiz"), ("期中考试我只考了61分。{q}", "61分"),
          ("I got an F on the essay. {q}", "I got an F"), ("My score was 45/60 on the test. {q}", "My score was 45/60"),
          ("I failed my first exam. {q}", "I failed my first exam"), ("I got 9/10 on the lab report. {q}", "I got 9/10"),
          ("My result was 52% on the practice test. {q}", "My result was 52%"), ("I received an A on the project. {q}", "I received an A")]
for text, g in GRADES:
    add("positive", "grade", text.format(q=q(), ql=ql()), [("GRADE", g)])

# HEALTH_DETAIL (self, family, ongoing, medicines, readings, owned items)
HEALTH = [
    ("self_condition", "I have asthma. {q}", "asthma"), ("ongoing", "I've been having migraines every week. {q}", "migraines"),
    ("family_medicine", "My dad takes metformin for his diabetes. {q}", "metformin"),
    ("family_diagnosis", "My mother was diagnosed with type 2 diabetes last year. {q}", "type 2 diabetes"),
    ("owned_item", "I use my inhaler before running. {q}", "inhaler"),
    ("self_event", "I was hospitalized with pneumonia in March. {q}", "pneumonia"),
    ("owned_item", "My blood pressure meds make me dizzy. {q}", "meds"),
    ("self_condition", "I have high blood pressure and I'm 22. {q}", "high blood pressure"),
    ("family_condition", "My sister has epilepsy. {q}", "epilepsy"), ("self_medicine", "I'm on lisinopril. {q}", "lisinopril"),
    ("family_event", "My grandfather had a stroke. {q}", "stroke"), ("ongoing", "I've been feeling depressed lately. {q}", "depressed"),
    ("owned_item", "My therapist suggested I ask. {q}", "therapist"),
    ("self_symptom", "I get chest pains when I climb stairs. {q}", "chest pains"),
    ("family_condition", "My roommate has an eating disorder. {q}", "eating disorder"), ("self_condition", "I am pregnant. {q}", "pregnant"),
    ("self_condition", "I'm asthmatic. {q}", "asthmatic"), ("family_condition", "My brother has hypertension. {q}", "hypertension"),
    ("self_medicine", "I take ventolin twice a day. {q}", "ventolin"), ("ongoing", "I've had headaches all week. {q}", "headaches"),
    ("family_medicine", "My mom uses insulin every day. {q}", "insulin"), ("self_condition", "I have type 1 diabetes. {q}", "type 1 diabetes"),
    ("self_reading", "My blood pressure was 150 over 95 this morning. {q}", "150 over 95"),
    ("owned_item", "My blood sugar is always high after lunch. {q}", "blood sugar"),
    ("self_symptom", "I feel dizzy when I stand up. {q}", "dizzy"), ("family_condition", "My son has allergies. {q}", "allergies"),
    ("self_condition", "I have anxiety. {q}", "anxiety"), ("family_event", "My aunt had a heart attack last year. {q}", "heart attack"),
    ("self_event", "I had surgery last month. {q}", "surgery"), ("owned_item", "My prescription ran out. {q}", "prescription"),
    ("self_medicine", "I'm taking antibiotics right now. {q}", "antibiotics"), ("ongoing", "I've been wheezing at night. {q}", "wheezing"),
    ("family_condition", "My girlfriend has migraines. {q}", "migraines"), ("self_condition", "I have ADHD. {q}", "ADHD"),
    ("owned_item", "My symptoms got worse yesterday. {q}", "symptoms"), ("self_condition", "I've got COVID. {q}", "COVID"),
]
for variant, text, term in HEALTH:
    add("positive", f"health_{variant}", text.format(q=q()), [("HEALTH_DETAIL", term)], personal_health=True)

# combinations
for i in range(20):
    n, s = NAMES[i], sid()
    first = n.split()[0].lower()
    if i % 2 == 0:
        add("positive", "combo_name_id_health", f"I'm {n}, student {s}, and I have asthma. Is exercise a good idea in general?",
            [("PERSON", n), ("STUDENT_ID", s), ("HEALTH_DETAIL", "asthma")], personal_health=True, self_name=n)
    else:
        add("positive", "combo_name_email_grade", f"This is {n} ({first}@uottawa.ca), I got 55/100 on the quiz. {q()}",
            [("PERSON", n), ("EMAIL_ADDRESS", f"{first}@uottawa.ca"), ("GRADE", "I got 55/100")], self_name=n)

# =============================================================== negative
NEG = [
    ("What is asthma?", ["asthma"]), ("Can you explain Cohen's kappa?", ["Cohen's kappa"]),
    ("Dr. Abbas said we should ask: why does salt raise blood pressure?", ["Abbas"]),
    ("How is the Brier score used to evaluate predictions?", ["Brier score"]), ("What is Parkinson's disease?", ["Parkinson's disease"]),
    ("What does the ELG 5902 course cover about hypertension?", ["ELG 5902"]),
    ("Is a reading of 140/90 considered high in general?", ["140/90"]), ("I have a question about migraines.", ["migraines"]),
    ("Why do people take metformin?", ["metformin"]), ("What is a normal blood pressure for adults?", ["normal blood pressure"]),
    ("Explain the Framingham risk score.", ["Framingham"]), ("How does an inhaler deliver medicine to the lungs?", ["inhaler"]),
    ("What is the DASH diet?", ["DASH"]), ("Tell me about Alzheimer's disease and blood pressure.", ["Alzheimer's disease"]),
    ("Why is hypertension called a silent killer?", ["hypertension"]), ("Can children get type 2 diabetes?", ["type 2 diabetes"]),
    ("Is 120/80 normal?", ["120/80"]), ("What does mmHg mean?", ["mmHg"]), ("How many grams of salt per day is recommended?", ["grams"]),
    ("Explain the Bland-Altman plot for blood pressure monitors.", ["Bland-Altman"]), ("What is the Glasgow Coma Scale?", ["Glasgow Coma Scale"]),
    ("Who should get a pneumonia vaccine?", ["pneumonia vaccine"]),
    ("My question is about chapter 3: what causes high blood pressure?", ["chapter 3"]),
    ("Prof. Abbas mentioned the DASH study, what did it find?", ["Abbas"]),
    ("What did the SPRINT trial show about blood pressure targets?", ["SPRINT"]), ("How do beta blockers lower blood pressure?", ["beta blockers"]),
    ("What is white coat hypertension?", ["white coat hypertension"]), ("Why do some people with asthma use two inhalers?", ["asthma"]),
    ("Is 50 percent of adults with hypertension unaware of it?", ["50 percent"]),
    ("What does a score of 7/10 on a pain scale mean for migraines?", ["7/10"]),
    ("How does Lipinski's rule of five apply to drugs?", ["Lipinski's rule"]), ("When was the Apgar score introduced?", ["Apgar score"]),
    ("What is the Mediterranean diet and does it help?", ["Mediterranean"]), ("What is Cushing's syndrome?", ["Cushing's syndrome"]),
    ("Explain the Kaplan-Meier curve for survival data.", ["Kaplan-Meier"]), ("What is Hashimoto's thyroiditis?", ["Hashimoto's"]),
    ("Why do doctors use the Wells score for clots?", ["Wells score"]), ("How does the Bohr effect relate to breathing?", ["Bohr effect"]),
    ("What is the Fick principle in cardiology?", ["Fick principle"]), ("Is the Mantoux test related to pneumonia?", ["Mantoux test"]),
    ("What do the guidelines from Hypertension Canada recommend?", ["Hypertension Canada"]),
    ("What does the WHO say about salt intake?", ["WHO"]), ("Is 6.5% HbA1c the cut-off for diabetes?", ["6.5%"]),
    ("Why is a peak flow of 400 L/min normal for some adults?", ["400 L/min"]),
    ("What does the 2017 ACC/AHA guideline define as stage 1?", ["ACC/AHA"]),
    ("For the quiz on Friday, should we know the DASH diet?", ["DASH"]), ("Can you summarize lecture 5 on asthma triggers?", ["lecture 5"]),
    ("What is a typical GPA requirement for medical school?", ["GPA"]), ("How is a 58/100 risk score interpreted in general?", ["58/100"]),
    ("Do patients with diabetes need insulin forever?", ["insulin"]),
]
for text, keep in NEG:
    add("negative", "curated", text, keep=keep)
for qq in BANK[:62]:
    add("negative", "plain_question", qq)

# =============================================================== hard
HARD = [
    ("lowercase_name", "hey its lucas bergeron, why does salt raise blood pressure?", [("PERSON", "lucas bergeron")], False, "Lucas Bergeron"),
    ("lowercase_name", "im maya okafor btw, what is the dash diet?", [("PERSON", "maya okafor")], False, "Maya Okafor"),
    ("lowercase_name", "priya raman here, how do inhalers work?", [("PERSON", "priya raman")], False, "Priya Raman"),
    ("pinyin_name", f"Hello, I am {PINYIN[0]}. {q()}", [("PERSON", PINYIN[0])], False, PINYIN[0]),
    ("pinyin_name", f"My classmate {PINYIN[1]} asked: {q()}", [("PERSON", PINYIN[1])], False, None),
    ("pinyin_name", f"{PINYIN[2]} here. {q()}", [("PERSON", PINYIN[2])], False, PINYIN[2]),
    ("chinese_name", "我是李明轩，学号300418277。What causes asthma?", [("PERSON", "李明轩"), ("STUDENT_ID", "300418277")], False, None),
    ("chinese_name", "我叫王芳。How is diabetes diagnosed?", [("PERSON", "王芳")], False, None),
    ("first_name_only", f"Tom here (tom.n@uottawa.ca). {q()}", [("PERSON", "Tom"), ("EMAIL_ADDRESS", "tom.n@uottawa.ca")], False, "Tom Nguyen"),
    ("first_name_only", f"Thanks, Ngozi again. {q()}", [("PERSON", "Ngozi")], False, "Ngozi Adeyemi"),
    ("embedded_name", "As Aisha Mohammed, a nursing student, I want to know what a stroke is.", [("PERSON", "Aisha Mohammed")], False, "Aisha Mohammed"),
    ("embedded_name", "Ask Dr. Wei Zhang, my doctor, about it? Why do people need pills daily?", [("PERSON", "Wei Zhang")], False, None),
    ("family_short_name", "My mom (Ana) has hypertension. Does it run in families?", [("PERSON", "Ana"), ("HEALTH_DETAIL", "hypertension")], True, None),
    ("id_spaced_digits", "my id is 3 0 0 4 1 8 2 7 7, why do we measure twice?", [("STUDENT_ID", "3 0 0 4 1 8 2 7 7")], False, None),
    ("id_typo_context", "my studnet number is 300418277, what is hypertension?", [("STUDENT_ID", "300418277")], False, None),
    ("id_spaced_no_context", "300 418 277 — can you explain the DASH diet?", [("STUDENT_ID", "300 418 277")], False, None),
    ("phone_no_separator", "Call me at 6135550142 later. What is a migraine?", [("PHONE_NUMBER", "6135550142")], False, None),
    ("phone_words", "my number is six one three five five five zero one four two. what is asthma?",
     [("PHONE_NUMBER", "six one three five five five zero one four two")], False, None),
    ("email_obfuscated", "Email: priya.raman AT uottawa DOT ca. What is the DASH diet?", [("EMAIL_ADDRESS", "priya.raman AT uottawa DOT ca")], False, None),
    ("email_obfuscated", "reach me at maya[at]gmail[dot]com, what triggers asthma?", [("EMAIL_ADDRESS", "maya[at]gmail[dot]com")], False, None),
    ("health_misspelled", "I have asthama, can I run in general?", [("HEALTH_DETAIL", "asthama")], True, None),
    ("health_casual", "my bp was 150/95 this morning, is that bad?", [("HEALTH_DETAIL", "150/95")], True, None),
    ("health_implicit", "Since my diagnosis I keep forgetting my pills. Why are they needed daily?", [("HEALTH_DETAIL", "diagnosis")], True, None),
    ("health_long_gap", "I've had asthma since I was a kid, can I still run a marathon in general?", [("HEALTH_DETAIL", "asthma")], True, None),
    ("health_third_person_self", "Asking for a friend (it's me): what helps with migraines? I get them every week.",
     [("HEALTH_DETAIL", "I get them every week")], True, None),
    ("grade_casual", "bombed the midterm with a 41, how do i study pharmacology?", [("GRADE", "41")], False, None),
    ("grade_relative", "I was 5 points below the class average. What is the DASH diet?", [("GRADE", "5 points below the class average")], False, None),
    ("name_with_number", "Tom Becker 300477120 asking about salt.", [("PERSON", "Tom Becker"), ("STUDENT_ID", "300477120")], False, "Tom Becker"),
    ("name_after_comma", f"{q()} — thanks, Olivia Brown", [("PERSON", "Olivia Brown")], False, "Olivia Brown"),
    ("hyphenated_name", f"Hi, I'm Jean-Luc Picard-Smith. {q()}", [("PERSON", "Jean-Luc Picard-Smith")], False, "Jean-Luc Picard-Smith"),
]
for variant, text, ents, health, self_name in HARD:
    add("hard", variant, text, ents, personal_health=health, self_name=self_name)

# =============================================================== french
FRENCH = [
    ("fr_name", "Je m'appelle Chloé Martin. Pourquoi le sel augmente-t-il la tension?", [("PERSON", "Chloé Martin")], False, "Chloé Martin"),
    ("fr_name", "Bonjour, c'est Julien Lefebvre. Qu'est-ce que l'asthme?", [("PERSON", "Julien Lefebvre")], False, "Julien Lefebvre"),
    ("fr_name", "Mon amie Amélie Dubois se demande comment fonctionne l'insuline.", [("PERSON", "Amélie Dubois")], False, None),
    ("fr_id", "Mon numéro étudiant est 300418277. Qu'est-ce que l'hypertension?", [("STUDENT_ID", "300418277")], False, None),
    ("fr_id", "Numéro d'étudiant : 300512345. Comment mesurer la tension?", [("STUDENT_ID", "300512345")], False, None),
    ("fr_email", "Mon courriel est julien.lefebvre@uottawa.ca. Qu'est-ce que le régime DASH?", [("EMAIL_ADDRESS", "julien.lefebvre@uottawa.ca")], False, None),
    ("fr_phone", "Mon numéro de téléphone est le 613-555-0100. Qu'est-ce que l'asthme?", [("PHONE_NUMBER", "613-555-0100")], False, None),
    ("fr_grade", "J'ai eu 58/100 à l'examen. Comment étudier la pharmacologie?", [("GRADE", "J'ai eu 58/100")], False, None),
    ("fr_health", "J'ai de l'asthme. Est-ce que je peux courir?", [("HEALTH_DETAIL", "asthme")], True, None),
    ("fr_health", "Ma mère prend de la metformine. Pourquoi?", [("HEALTH_DETAIL", "metformine")], True, None),
    ("fr_health", "Je fais des migraines chaque semaine. Que faire en général?", [("HEALTH_DETAIL", "migraines")], True, None),
    ("fr_health", "Mon père a fait un AVC l'an dernier. Quels sont les risques?", [("HEALTH_DETAIL", "AVC")], True, None),
    ("fr_combo", "Je suis Sophie Bélanger, étudiante 300777888, et j'ai du diabète.",
     [("PERSON", "Sophie Bélanger"), ("STUDENT_ID", "300777888"), ("HEALTH_DETAIL", "diabète")], True, "Sophie Bélanger"),
    ("fr_negative", "Qu'est-ce que la maladie de Parkinson?", [], False, None),
    ("fr_negative", "Pourquoi l'hypertension est-elle silencieuse?", [], False, None),
]
for variant, text, ents, health, self_name in FRENCH:
    add("french", variant, text, ents, personal_health=health, self_name=self_name)

# =============================================================== multi-turn
CONVS = [
    ("C01", "Lucas Bergeron", ["Hi, I'm Lucas Bergeron.", "Bergeron again — why does salt raise blood pressure?",
                               "Also, my student number is 300418277."],
     [[("PERSON", "Lucas Bergeron")], [("PERSON", "Bergeron")], [("STUDENT_ID", "300418277")]], [False, False, False]),
    ("C02", "Maya Okafor", ["What is asthma?", "Ok so I have it since childhood.", "Is running safe in general?"],
     [[], [("HEALTH_DETAIL", "I have it")], []], [False, True, False]),
    ("C03", "Priya Raman", ["My mom was just diagnosed.", "It's type 2 diabetes. What should she eat in general?"],
     [[("HEALTH_DETAIL", "diagnosed")], [("HEALTH_DETAIL", "type 2 diabetes")]], [True, True]),
    ("C04", "Tom Nguyen", ["Can you email me the summary?", "It's tom.nguyen@uottawa.ca", "Thanks Tom here"],
     [[], [("EMAIL_ADDRESS", "tom.nguyen@uottawa.ca")], [("PERSON", "Tom")]], [False, False, False]),
    ("C05", "Aisha Mohammed", ["I got a bad grade.", "It was 48 percent on the quiz.", "How should I study for the final?"],
     [[], [("GRADE", "48 percent")], []], [False, False, False]),
    ("C06", "Wei Zhang", ["What does the bottom number mean?", "Mine was 95 this morning, is that high?"],
     [[], [("HEALTH_DETAIL", "Mine was 95")]], [False, True]),
    ("C07", "Sofia Rossi", ["I'm Sofia.", "Rossi, from section A.", "What is the DASH diet?"],
     [[("PERSON", "Sofia")], [("PERSON", "Rossi")], []], [False, False, False]),
    ("C08", "Kwame Mensah", ["My phone is 613-555-0175.", "Call if the answer is long. What is pneumonia?"],
     [[("PHONE_NUMBER", "613-555-0175")], []], [False, False]),
]
for conv, self_name, turns, ents, health in CONVS:
    for t, (text, es, h) in enumerate(zip(turns, ents, health, strict=True)):
        add("multiturn", f"turn{t + 1}", text, es, personal_health=h, self_name=self_name, conversation=conv)

# =============================================================== out of scope (known gaps)
OOS = [
    ("address", "I live at 75 Laurier Ave E, Ottawa. Is the air there bad for asthma?", "75 Laurier Ave E"),
    ("address", "My apartment is 1200 Bank Street, unit 4. Is there a pharmacy nearby?", "1200 Bank Street, unit 4"),
    ("date_of_birth", "I was born on 12 March 2003. At what age should blood pressure be checked?", "12 March 2003"),
    ("date_of_birth", "DOB: 2004-07-15. Does age matter for asthma?", "2004-07-15"),
    ("health_card", "My OHIP number is 1234-567-890-AB. Does it cover blood pressure monitors?", "1234-567-890-AB"),
    ("health_card", "Health card 9876 543 210 XY, is the flu shot free?", "9876 543 210 XY"),
    ("postal_code", "My postal code is K1N 6N5, is there a clinic nearby?", "K1N 6N5"),
    ("postal_code", "I'm in K2P1L4, where can I get my blood pressure checked?", "K2P1L4"),
    ("age", "I'm 19 years old, can I have high blood pressure?", "19 years old"),
    ("age", "At 52 is it normal to have higher readings?", "At 52"),
    ("sin", "My SIN is 046 454 286, do I need it for the clinic?", "046 454 286"),
    ("workplace", "I work at the Ottawa Hospital, General Campus. What is pneumonia?", "Ottawa Hospital"),
    ("school", "I study at Lisgar Collegiate. What is the DASH diet?", "Lisgar Collegiate"),
    ("social_handle", "Find me on instagram @maya_okafor22. What is the DASH diet?", "@maya_okafor22"),
    ("url", "My blog is mayahealthjournal.wordpress.com, is my diet advice correct?", "mayahealthjournal.wordpress.com"),
    ("license_plate", "My car plate is CDKX 123, can stress raise blood pressure while driving?", "CDKX 123"),
    ("ip_address", "My laptop IP is 192.168.2.44 and the tutor is slow. What is asthma?", "192.168.2.44"),
    ("clinic_mrn", "My hospital record number is MRN 00451237. What does it say about asthma?", "MRN 00451237"),
]
for variant, text, val in OOS:
    add("out_of_scope", variant, text, [(variant.upper(), val)])

out = HERE / "cases.jsonl"
out.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in cases) + "\n", encoding="utf-8")
counts: dict[str, int] = {}
for c in cases:
    counts[c["group"]] = counts.get(c["group"], 0) + 1
print(f"{len(cases)} cases -> {out}  {counts}")
