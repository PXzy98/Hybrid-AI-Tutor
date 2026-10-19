# E4: privacy audit of cloud requests (design §11 E4)

1 personas × 274 questions = 274 asks, all forced to the cloud route; provider: local echo (nothing left the machine).

Targets: fields outside the allow-list: 0 · profile or identity leak: 0 · PII leak ≤ 1% ideal / 5% marginal.

| Result | Value |
|---|---|
| Cloud requests recorded | 217 (from 217 asks) |
| Asks kept local (not cloud-safe, or blocked by the pre-send guard) | 57 (guard warnings: 1) |
| Fields outside the allow-list | 0 |
| Identity leaks | 0 |
| Profile leaks | 0 |
| PII leaks in cloud requests | 15 (6.9% of requests) |
| Personal health questions that reached the cloud | 5 of 61 |
| Typed PII or identity stored in the DB or logs | 20 |

## Findings

- **pii** in cloud#162: typed value 'lucas bergeron'
- **pii** in cloud#164: typed value 'priya raman'
- **pii** in cloud#174: typed value '3 0 0 4 1 8 2 7 7'
- **pii** in cloud#176: typed value '300 418 277'
- **pii** in cloud#177: typed value '6135550142'
- **pii** in cloud#178: typed value 'six one three five five five zero one four two'
- **pii** in cloud#179: typed value 'priya.raman AT uottawa DOT ca'
- **pii** in cloud#181: typed value 'asthama'
- **pii** in cloud#182: typed value 'I get them every week'
- **pii** in cloud#183: typed value '41'
- **pii** in cloud#184: typed value '5 points below the class average'
- **pii** in cloud#201: typed value 'I have it'
- **pii** in cloud#203: typed value 'diagnosed'
- **pii** in cloud#204: typed value 'type 2 diabetes'
- **pii** in cloud#209: typed value '48 percent'
- **health** in cloud#181: personal health question reached the cloud: 'I have asthama, can I run in general?'
- **health** in cloud#182: personal health question reached the cloud: 'Asking for a friend (it's me): what helps with migraines? I '
- **health** in cloud#201: personal health question reached the cloud: 'Ok so I have it since childhood.'
- **health** in cloud#203: personal health question reached the cloud: 'My mom was just diagnosed.'
- **health** in cloud#204: personal health question reached the cloud: 'It's type 2 diabetes. What should she eat in general?'
- **pii** in db: raw typed value stored 'inhaler' (ask: 'I use my inhaler before running. Is exercise enoug')
- **pii** in db: raw typed value stored 'insulin' (ask: 'My mom uses insulin every day. What foods are best')
- **pii** in db: raw typed value stored 'prescription' (ask: 'My prescription ran out. is swimming really bad fo')
- **pii** in db: raw typed value stored 'symptoms' (ask: 'My symptoms got worse yesterday. hydration matters')
- **pii** in db: raw typed value stored 'lucas bergeron' (ask: 'hey its lucas bergeron, why does salt raise blood ')
- **pii** in db: raw typed value stored 'priya raman' (ask: 'priya raman here, how do inhalers work?')
- **pii** in db: raw typed value stored '3 0 0 4 1 8 2 7 7' (ask: 'my id is 3 0 0 4 1 8 2 7 7, why do we measure twic')
- **pii** in db: raw typed value stored '300 418 277' (ask: '300 418 277 — can you explain the DASH diet?')
- **pii** in db: raw typed value stored '6135550142' (ask: 'Call me at 6135550142 later. What is a migraine?')
- **pii** in db: raw typed value stored 'six one three five five five zero one four two' (ask: 'my number is six one three five five five zero one')
- **pii** in db: raw typed value stored 'priya.raman AT uottawa DOT ca' (ask: 'Email: priya.raman AT uottawa DOT ca. What is the ')
- **pii** in db: raw typed value stored 'asthama' (ask: 'I have asthama, can I run in general?')
- **pii** in db: raw typed value stored '150/95' (ask: 'my bp was 150/95 this morning, is that bad?')
- **pii** in db: raw typed value stored 'I get them every week' (ask: 'Asking for a friend (it's me): what helps with mig')
- **pii** in db: raw typed value stored '41' (ask: 'bombed the midterm with a 41, how do i study pharm')
- **pii** in db: raw typed value stored '5 points below the class average' (ask: 'I was 5 points below the class average. What is th')
- **pii** in db: raw typed value stored 'I have it' (ask: 'Ok so I have it since childhood.')
- **pii** in db: raw typed value stored 'diagnosed' (ask: 'My mom was just diagnosed.')
- **pii** in db: raw typed value stored 'type 2 diabetes' (ask: 'It's type 2 diabetes. What should she eat in gener')
- **pii** in db: raw typed value stored '48 percent' (ask: 'It was 48 percent on the quiz.')

## Asks kept local

- novice: I have asthma. Is metformin usually the first med prescribed?
- novice: I've been having migraines every week. Do natural remedies help at all really?
- novice: My dad takes metformin for his diabetes. Whats the main goal of a treatment plan?
- novice: My mother was diagnosed with type 2 diabetes last year. Do stress and exams spike blood sugar specifically?
- novice: I use my inhaler before running. Is exercise enough without diet changes?
- novice: I was hospitalized with pneumonia in March. Are there any herbal teas safe to drink regularly?
- novice: My blood pressure meds make me dizzy. is it normal to cough up green mucus for weeks?
- novice: I have high blood pressure and I'm 22. what is the most common complication after getting sick?
- novice: My sister has epilepsy. Can smoking actually raise your blood pressure permanently?
- novice: I'm on lisinopril. So what exactly is insulin resistance?
- novice: My grandfather had a stroke. what is the most common complication after getting sick?
- novice: I've been feeling depressed lately. Why do we need to monitor ketones sometimes?
- novice: My therapist suggested I ask. hydration matters?
- novice: I get chest pains when I climb stairs. Can you explain the difference between pre and post prandial blood sugar?
- novice: My roommate has an eating disorder. what are common side effects of steroids?
- novice: I am pregnant. What does a peak flow meter do exactly?
- novice: I'm asthmatic. Can alcohol really affect blood pressure readings?
- novice: My brother has hypertension. any tips for writing an essay on this topic?
- novice: I take ventolin twice a day. So what exactly causes hypertension?
- novice: I've had headaches all week. How long after starting a diet do we see results?
- novice: My mom uses insulin every day. What foods are best for high blood pressure?
- novice: I have type 1 diabetes. is it normal to cough up green mucus for weeks?
- novice: My blood pressure was 150 over 95 this morning. what is the most common complication after getting sick?
- novice: My blood sugar is always high after lunch. are there natural remedies that work well?
- novice: I feel dizzy when I stand up. How long after starting a diet do we see results?
- novice: My son has allergies. Can you explain systolic vs diastolic simply?
- novice: I have anxiety. any tips for writing an essay on this topic?
- novice: My aunt had a heart attack last year. Why does it feel harder to manage in winter?
- novice: I had surgery last month. what is the main cause of community acquired pneumonia?
- novice: My prescription ran out. is swimming really bad for lungs here?
- novice: I'm taking antibiotics right now. How often do we need to check our pressure at home?
- novice: I've been wheezing at night. hydration matters?
- novice: My girlfriend has migraines. Can you explain the difference between pre and post prandial blood sugar?
- novice: I have ADHD. Can you explain the difference between pre and post prandial blood sugar?
- novice: My symptoms got worse yesterday. hydration matters?
- novice: I've got COVID. why do some patients need a ventilator even briefly?
- novice: I'm Maya Okafor, student 300608217, and I have asthma. Is exercise a good idea in general?
- novice: I'm Maya Okafor, student 300716382, and I have asthma. Is exercise a good idea in general?
- novice: I'm Maya Okafor, student 300780839, and I have asthma. Is exercise a good idea in general?
- novice: I'm Maya Okafor, student 300050394, and I have asthma. Is exercise a good idea in general?
- novice: I'm Maya Okafor, student 300329015, and I have asthma. Is exercise a good idea in general?
- novice: I'm Maya Okafor, student 300689511, and I have asthma. Is exercise a good idea in general?
- novice: I'm Maya Okafor, student 300430788, and I have asthma. Is exercise a good idea in general?
- novice: I'm Maya Okafor, student 300186240, and I have asthma. Is exercise a good idea in general?
- novice: I'm Maya Okafor, student 300768124, and I have asthma. Is exercise a good idea in general?
- novice: I'm Maya Okafor, student 300691147, and I have asthma. Is exercise a good idea in general?
- novice: My mom (Ana) has hypertension. Does it run in families?
- novice: my bp was 150/95 this morning, is that bad?
- novice: Since my diagnosis I keep forgetting my pills. Why are they needed daily?
- novice: I've had asthma since I was a kid, can I still run a marathon in general?
- novice: Mon amie Amélie Dubois se demande comment fonctionne l'insuline.
- novice: J'ai de l'asthme. Est-ce que je peux courir?
- novice: Ma mère prend de la metformine. Pourquoi?
- novice: Je fais des migraines chaque semaine. Que faire en général?
- novice: Mon père a fait un AVC l'an dernier. Quels sont les risques?
- novice: Je suis Maya Okafor, étudiante 300777888, et j'ai du diabète.
- novice: Mine was 95 this morning, is that high?

**Verdict: LEAK — release blocked (design §11 E4)**
