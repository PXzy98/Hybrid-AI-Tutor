# Student manual

For students of a course that uses the Course Tutor. Interface labels are quoted as they appear in the
English interface (French is available through the language switch). The instructor manual is
[INSTRUCTOR_MANUAL.md](INSTRUCTOR_MANUAL.md).

The tutor is for learning only. It can make mistakes: check important facts against your course material.

## 1. Joining a course

1. Get the **invitation code** from your instructor.
2. Open the **Join a course** page (the link "Have an invitation code?" on the login page).
3. New to the system: fill in **Invitation code**, **E-mail address**, **Your name** and **Choose a password**,
   then **Join**. This step creates your account. Your e-mail address must already be on the class list your
   instructor imported: the code alone, or an address of an allowed domain (`uottawa.ca` by default), is not
   enough. The password needs at least 10 characters.
4. Already have an account: log in, use **Join a course** in the sidebar and enter only the code.
5. Importing the class list does not create accounts; it only reserves a place for each e-mail address until
   the student joins. If you logged in with a temporary password (after a reset) you must choose your own first
   ("Choose your password").

Your instructor can reset your password; you then get a temporary one and choose a new one at the next login.
Codes expire (120 days by default); ask for a new one if yours does not work.

## 2. Choosing a course and a module

**My courses** lists your courses; open one to get the student dashboard. The sidebar shows the course's
**Modules**: pick one to ask about that module, or **Whole course** to ask about everything including
syllabus and project requirements. **Conversations** lists your earlier chats; **New chat** starts a new one.
A conversation belongs to one course. The dashboard has five tabs: **Chat**, **My progress**,
**Personalize**, **Quizzes**, **End-of-term survey**.

## 3. Asking questions (Chat)

- Type under **Your question** and press **Send**. Or start from **Suggested questions**.
- Ask in **English**: course content and answers are in English for now, and the privacy filter only
  recognizes English.
- "Asking about:" shows the module or the whole course. "Explained at level" shows the level the tutor uses
  for you. If you have not personalized the tutor, "Answers are not adapted to you yet." links to
  **Personalize your tutor**.
- Under an answer you may see **Sources** (the course files and the page or slide the answer is based on),
  a "Check your understanding" question, and "Suggested next:".
- If your instructor switched it on, **Routing steps** shows how the tutor decided where to answer.

### Local model or cloud model

Each answer has a label:

| Label | Meaning |
|---|---|
| **Local model** | The answer was written by the course's own model. |
| **Cloud model** | Came from a cloud model. Personal details were removed from the question first. |

The label tells you which model wrote the answer, not whether anything left the server. For example, if the
tutor sent the (privacy-filtered) question to the cloud model and the cloud call failed, the local model
answers instead and the label shows **Local model**; a warning under the answer then says "The cloud model was
unavailable, so the local model answers" (other warnings explain, for example, a privacy check or a local-only
course). Only a course set to **local only** guarantees that no question is sent to a cloud model.

The permanent notice in the chat says: your question goes through a **privacy filter** first; depending on the
question it may be sent to a cloud model with personal details removed. **Do not type personal or health
information.** Questions that contain personal details stay on the local model or are sent only as a general
rewrite without them. An instructor can also make a course **local only**: then no question is ever sent to a
cloud model.

### What is not stored

- The tutor does not store or log your question text in its logs, statistics or learner profile. Your
  instructor can never read what you asked.
- To let you reopen a conversation, the server keeps a sanitized transcript (personal details removed) of your
  own conversations. Only you see it, and it is deleted when you delete your data (section 9) and at the end of
  term.
- The tutor records numbers and labels about what you know (section 4), not words.

## 4. My progress

**My progress** shows what the tutor thinks you know, per topic (knowledge component), in bands:
**basic**, **intermediate**, **advanced**, **mastered**, **not assessed**. It also shows "Ideas we are working
on", "A common mix-up:" with "What is true:" for misconceptions the tutor noticed (marked "seen in your
answers" or "may have come up in a question"), and your explanation preferences. You are never graded: the
bands are only there to adapt answers.

**Personalize** (optional, every part can be skipped, you can change everything later):
1. **Your learning profile**: consent that the tutor keeps a learning profile for you. Without consent your
   answers are not saved and the tutor answers without a profile.
2. **How you like to learn**: example first or idea first, short or detailed answers.
3. **Quick check of what you already know**: a few questions for one module (the course diagnostic).

## 5. What your instructor can see

The course is in one of two modes, shown under **What your instructor can see** on **My progress**, in the
chat banner and during **Personalize**.

| Mode | The instructor sees |
|---|---|
| **A** | Only anonymous class totals, never your own progress. Totals are hidden when fewer than 5 students share them. |
| **B** | Your individual progress and a learning plan, but only after you agree. |

In mode B:
- **I understand and agree** starts the sharing. The instructor then sees your progress bands, open
  misconceptions, check-question counts, quiz results, your answer style (example or idea first, short or
  detailed) if you set or change it afterwards, and when you were last active, **only from that moment on**
  (older data stays hidden).
- **Stop sharing with my instructor** (opt out): "Your instructor cannot see your progress." The instructor sees
  that you chose not to share, nothing individual, and cannot write a plan for you. Your data still counts in
  the class totals and the tutor still adapts to you.
- **Share again** opts back in; sharing then starts from that moment.
- If the instructor switches the course back to mode A, sharing stops immediately. If it is switched to B again
  you are asked again.
- Every time an instructor opens an individual view it is written to an audit log.

The instructor **cannot** see: what you asked (it is never stored), the answers you were given, your
conversations, your consent text, anything from before you agreed, or anything at all if you
opted out or the mode is A.

## 6. Learning plan

In mode B, after you agreed, the instructor may write a plan: a **Goal level**, **Focus topics** and **Notes**.
You see it under **Learning plan** on **My progress**; it is read-only for you.

## 7. Quizzes

**Quizzes** lists the quizzes your instructor published for you. They are short multiple choice and true/false
questions for checking your progress. **They are not grades.**
- You can answer **once**. Open the quiz while it is open (see Opens/Closes), answer every question and press
  **Submit answers**. The result and the explanations appear right away and stay visible afterwards.
- A closed quiz you did not answer shows nothing.
- If you gave consent, your answers also update your progress bands.
- The instructor sees class totals (once at least 5 students answered) and, only in mode B after you agreed,
  your own score. A **final** quiz is compared with your diagnostic answers ("Before and after").

## 8. End-of-term survey

In the survey window your instructor sets, **End-of-term survey** shows five statements about how the tutor
helped you. Rate each from 1 (not at all) to 5 (very much), then **Submit survey**. You answer once.
It is anonymous: your answers are saved without your name, ID or time. A separate record only notes that you
answered, so that nobody answers twice, and it cannot be linked to your ratings. There is no free text. The
instructor sees averages only, and only when at least 3 students answered.

## 9. Deleting my data in a course

On **My progress**, **Delete my learning data in this course** removes your learning profile, progress bands,
answers to check questions and quizzes, and your conversations in this course. Other courses, your account,
preferences and consent stay. It cannot be undone. (Your anonymous survey answer cannot be found again, so it
stays until the end of term.)

## 10. End of term

When the instructor ends the term, the course's student data is exported by the instructor (class totals and,
only for students who share in mode B, the individual progress the instructor may already see) and then
deleted: your membership, profile, evidence, plan, conversations, quiz attempts and survey data. Your account
stays, so you can join next term's course with a new code. Published quizzes are closed.
