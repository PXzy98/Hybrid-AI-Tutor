# E4: privacy audit of cloud requests (design §11 E4)

1 personas × 274 questions = 274 asks, all forced to the cloud route; provider: local echo (nothing left the machine).

Targets: fields outside the allow-list: 0 · profile or identity leak: 0 · PII leak ≤ 1% ideal / 5% marginal.

| Result | Value |
|---|---|
| Cloud requests recorded | 272 (from 272 asks) |
| Asks kept local (not cloud-safe, or blocked by the pre-send guard) | 2 (privacy notices: 2) |
| Personal health questions sent as a checked hypothetical rewrite | 55 |
| Fields outside the allow-list | 0 |
| Identity leaks | 0 |
| Profile leaks | 0 |
| PII leaks in cloud requests | 10 (3.7% of requests) |
| Personal health questions that reached the cloud as a personal statement (policy: generalize) | 4 of 61 |
| Typed PII or identity stored in the DB or logs | 15 |

## Findings

- **pii** in cloud#207: typed value 'lucas bergeron'
- **pii** in cloud#209: typed value 'priya raman'
- **pii** in cloud#220: typed value '3 0 0 4 1 8 2 7 7'
- **pii** in cloud#222: typed value '300 418 277'
- **pii** in cloud#223: typed value '6135550142'
- **pii** in cloud#224: typed value 'six one three five five five zero one four two'
- **pii** in cloud#225: typed value 'priya.raman AT uottawa DOT ca'
- **pii** in cloud#232: typed value '41'
- **pii** in cloud#233: typed value '5 points below the class average'
- **pii** in cloud#263: typed value '48 percent'
- **health** in cloud#227: personal health statement reached the cloud (not generalized): 'I have asthama, can I run in general?'
- **health** in cloud#231: personal health statement reached the cloud (not generalized): 'Asking for a friend (it's me): what helps with migraines? I '
- **health** in cloud#255: personal health statement reached the cloud (not generalized): 'Ok so I have it since childhood.'
- **health** in cloud#257: personal health statement reached the cloud (not generalized): 'My mom was just diagnosed.'
- **pii** in db: raw typed value stored 'lucas bergeron' (ask: 'hey its lucas bergeron, why does salt raise blood ')
- **pii** in db: raw typed value stored 'priya raman' (ask: 'priya raman here, how do inhalers work?')
- **pii** in db: raw typed value stored '3 0 0 4 1 8 2 7 7' (ask: 'my id is 3 0 0 4 1 8 2 7 7, why do we measure twic')
- **pii** in db: raw typed value stored '300 418 277' (ask: '300 418 277 — can you explain the DASH diet?')
- **pii** in db: raw typed value stored '6135550142' (ask: 'Call me at 6135550142 later. What is a migraine?')
- **pii** in db: raw typed value stored 'six one three five five five zero one four two' (ask: 'my number is six one three five five five zero one')
- **pii** in db: raw typed value stored 'priya.raman AT uottawa DOT ca' (ask: 'Email: priya.raman AT uottawa DOT ca. What is the ')
- **pii** in db: raw typed value stored 'asthama' (ask: 'I have asthama, can I run in general?')
- **pii** in db: raw typed value stored 'I get them every week' (ask: 'Asking for a friend (it's me): what helps with mig')
- **pii** in db: raw typed value stored '41' (ask: 'bombed the midterm with a 41, how do i study pharm')
- **pii** in db: raw typed value stored '5 points below the class average' (ask: 'I was 5 points below the class average. What is th')
- **pii** in db: raw typed value stored 'I have it' (ask: 'Ok so I have it since childhood.')
- **pii** in db: raw typed value stored 'diagnosed' (ask: 'My mom was just diagnosed.')
- **pii** in db: raw typed value stored 'type 2 diabetes' (ask: 'It's type 2 diabetes. What should she eat in gener')
- **pii** in db: raw typed value stored '48 percent' (ask: 'It was 48 percent on the quiz.')

## Asks kept local

- novice: I'm taking antibiotics right now. How often do we need to check our pressure at home?
- novice: Mon amie Amélie Dubois se demande comment fonctionne l'insuline.

**Verdict: LEAK — release blocked (design §11 E4)**
