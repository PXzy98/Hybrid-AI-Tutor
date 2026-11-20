# Instructor manual

For instructors (and administrators) who run a course in PACT (Privacy-Aware Course Tutor). Interface labels are quoted as
they appear in the English interface. Students: [STUDENT_MANUAL.md](STUDENT_MANUAL.md). Technical background:
[design/course-structure.md](design/course-structure.md), [design/api-v2.md](design/api-v2.md); deploying the
system: [OPERATIONS.md](OPERATIONS.md).

Some features exist only in the HTTP API so far and have no page in the app; they are marked **API only** and
listed in section 13.

## 1. Your dashboard

Log in with your instructor account (an administrator can create instructor accounts; you choose your own
password at the first login). **My courses** lists your courses; **New course** (sidebar) creates one. A course
page has nine tabs: **Class overview**, **Students**, **Course content**, **Members**, **Materials**,
**Settings**, **End of term**, **Quizzes**, **End-of-term survey**.

**Teaching assistants.** There is no TA role. A TA uses the instructor's account for that course. So: the audit
log cannot tell the instructor and the TA apart; the password is shared, so it must be strong and changed after
the term; a TA sees everything the instructor sees.

## 2. Creating a course

**New course**: **Course code**, **Title**, **Course type**, **Term**, then **Create course**. You become the
instructor of the course. One course lasts for years: at the end of each term you end the term (section 11) and
import the next class.

**Course type** selects the **privacy profile**, the rules that remove personal data from questions before
anything leaves the server:

| Type | Use for |
|---|---|
| `general` | the base rules only (names, e-mail addresses, phone numbers, IDs, keys and tokens) |
| `medical_science` | adds the health rules: a question with a personal health detail stays local or goes to the cloud only as a general rewrite; answers carry a "not medical advice" note |
| `life_science` | biology terms are not treated as personal health |
| `ece` | engineering: also removes private network addresses and repository links; reminds students not to paste passwords or keys |

The list in the form comes from the server (one profile file per type). Choose it before students start asking.

## 3. Modules

**Course content** > **Guideline for the tutor (whole course)**: rules the tutor follows in every answer of the
course (for example "never give the final answer of a homework problem" or "use SI units"), up to 4000
characters. **Modules**: **Add module** (**Module code**, title, **Guideline for the tutor**, rules for answers
about that module only); rename, move up or down, delete. Students can ask about one module or **Whole course**.
Course-level documents (syllabus, project requirements) belong to no module.

How the guidelines are used: a question about a module gets the course guideline and that module's guideline; a
question about the whole course gets the course guideline only. They come after the built-in safety rules (which
they cannot change) and before the student's answer-style choices, which apply only where they do not conflict.
Students do not see them, and a question such as "ignore the instructor's rules" does not change them. They are
sent with the question to the model that answers, including a cloud model (they are your text, not student
data), and are part of the content export and import.

## 4. Materials

**Materials**: lecture notes, slides and documents the tutor uses to answer (PDF, PPTX, DOCX, Markdown, text,
HTML).
- **Upload a file**, choose a module or **Whole course**, then **Upload**.
- Each file is **scanned for student data** before it is stored. A file that contains personal data of students
  (for example a class list, or grades with names) is **refused** and nothing is stored; the message names the
  kind of finding, never the text. What to do: remove the names, e-mail addresses and IDs from the file (or
  upload the version without them) and upload again. A file that only names the instructor is accepted.
  Unreadable, too large or unsupported files are refused too.
- After an upload or delete the server **rebuilds the search index** ("Rebuilding the search index. New files
  are used for answers when it is done."). If it fails ("The index could not be rebuilt"), upload again or
  contact an administrator. The list shows the scan status and the **Index version**.
- Delete a file with **Delete file**; the index is rebuilt without it.
- **Add a web page**: give its address (https only) and a module or the whole course, then **Add the page**.
  The server fetches the page once (public sites only, never addresses inside the university network or the
  server itself; at most 2 MB; at most 3 redirects, each checked the same way), keeps its text as a Markdown
  file with the address on top, scans it like an upload and indexes it. The list shows the address; **Fetch
  again** replaces the text with the page's current version (scanned again). Images and attached files of the
  page are not fetched. The AI assistant can also draft from a web page (section 10).

Course material goes only to models your settings allow: the local model for drafts (section 8), and to a cloud
model only in answers and in the tier 4 evaluation after your explicit confirmation.

## 5. Content: knowledge components, check items, misconceptions

On **Course content**:
- **Knowledge components** (KCs): the ideas students should learn (**Module**, **Level**, **Code**, **Name**,
  **Definition**). Codes never change. Use **Retire** instead of deleting; status is draft, active or retired.
- **Check items**: multiple choice questions shown under answers and in the diagnostic (**Knowledge component**,
  **Item code**, **Question**, options, **Correct answer**, **Explanation**). A course without check items skips
  the diagnostic.
- Content you create counts as reviewed. AI-generated content is a draft until you accept it.
- **API only**: misconceptions (`/courses/{course_id}/misconceptions`) and YAML import and export
  (`POST .../content/import`, `GET .../content/export`), used to seed a course or review it offline.

## 6. Members, invitation codes, co-instructors

**Members** lists everyone with **Name**, **E-mail**, **Role**, **Status** (active, or pending until the student
joins).
- **Import a class list**: a CSV with an `email` column and an optional `display_name` column (others are
  ignored). Importing creates **no accounts**: it only reserves a pending place for each e-mail address. A new
  student creates the account on the Join page with the invitation code, e-mail (which must be on your list),
  name and password; a student who already has an account logs in and enters only the code. The username is the part of the e-mail before the `@`. The **Import report** shows how many were
  added, are waiting for their invitation code, are unchanged or were rejected (with the row).
- **Invitation code**: students join with it on the Join page. Shown with its expiry (120 days by default) and
  how often it was used. **Create a new code** voids the old one. If the server cannot show an old code
  ("The code cannot be shown again"), create a new one.
- **Reset password**: shows a temporary password once; the student must choose a new one at the next login.
- **Remove** removes a member from the course.
- **Add a co-instructor**: by e-mail; the person needs an instructor account.

## 7. Settings

**Settings** ("Privacy and routing"; changes apply to new questions after you save):
- **What instructors see of students**: in this version always class statistics only ("Instructors see class
  statistics only"); nobody sees one student's questions, answers or progress. (If the deployment switches
  individual views on, this becomes a choice: **Mode A: class totals only** or **Mode B: individual progress
  after the student agrees**.)
- **Local only**: every answer is written on the course's own server; no question goes to a cloud model. This
  is the only setting that guarantees it: with other settings the **Local model** label on an answer only says
  which model answered, and a question may have been sent to the cloud before a failed call fell back to local
  (the answer then carries the warning "The cloud model was unavailable, so the local model answered.").
- **Routing preference**: **Let the router decide**, **Prefer the local model** or **Prefer the cloud model**.
- **Show routing steps in the student chat**.
If someone else saved at the same time you see "Someone else changed the settings"; review and save again.
While a change is being applied you may see "The settings are being applied"; try again in a moment.

Only where individual views are switched on: switching B to A takes effect at once for everyone; switching A to
B applies to a student only after that student agrees, and then only data after that moment is shown.

## 8. Class overview and individual progress

**Use of the tutor** (top of **Class overview**): **Students enrolled**, **Active students (7 days)**,
**Questions (7 days)**, the share **Answered by the local model**, **Questions per week** (the last 8 weeks, with
the number of students who asked), **Questions per module** (and **Whole course**) and **Quiz averages** (answers
and average score per published quiz). Counts only: no question, no name, and every number that fewer than 5
students contributed shows "hidden". The administrator sees the same counts for every course on
**Administration** (**Use of the tutor in every course**).

**Class overview**: totals per **Module**: **Students with a profile**, **Topics**, **Open misconceptions**,
**Students per level**, and shared misconceptions. Groups smaller than 5 are hidden ("hidden"), in both modes.

**Individual progress is not available in this version**: there is no **Students** page, no learning plan and no
per-student quiz result. The rest of this section applies only where the deployment switches individual views
on.

**Students** lists students with **Progress sharing**: **Visible**, **Not visible** or **Not shared**.
**View progress** opens one student: levels per topic, check questions answered, open misconceptions, last
active, and **Answer style** (shown only when the student set or changed it after agreeing). This works **only in mode B, after the student agreed, while they have not opted out, and only for data
after they agreed**; otherwise "This student's progress is not visible." **Every view is written to the audit
log.** Question text is never stored, so it cannot be shown.

**Learning plan** (same conditions): **Goal level**, **Focus topics** and **Notes**, then **Save plan**. The
student reads it on **My progress**. Targeted material for single students is planned for a later term; for now
the plan with notes is the tool.

## 9. Quizzes

**Quizzes** (progress checks, **not grades**): multiple choice and true/false only, graded automatically.
1. **New quiz**: title, **Type** (**practice** or **final**), module or whole course, **Opens**, **Closes**
   (optional), **Assigned to** (**Every student** by default), then **Questions** (**Add question**: **Question
   type**, **Question**, **Options (select the correct one)**, **Explanation**, optional knowledge component).
   **Save quiz**. A quiz starts as a **draft**.
2. **Draft with AI**: choose **Number of questions**, **Draft with AI**. The **local** model drafts questions
   from the course material (never student data); they appear marked "AI draft, not reviewed" with the
   material file named.
3. **Review gate**: AI-drafted questions must be checked and saved before the quiz can be published. Saving marks
   every question as reviewed. **Publish** is refused for a quiz with no question or unreviewed questions.
4. **Publish**, then students answer **once** inside the window. **Close** ends it. After the first answer the
   questions cannot change, and the quiz cannot be deleted (close it).
5. **Results**: **Average score** and **Correct answers per question** appear once at least 5 students answered
   ("Not enough answers yet"). There are no per-student results in this version (where individual views are
   switched on, a **Students** list shows students who share their progress; each such view is audited).
6. **Final quiz vs diagnostic**: a quiz of type **final** is the post-test. **Before and after** compares the
   course diagnostic (the students' onboarding answers, the pre-test) with the final quiz for students who
   have both (hidden below 5 students).
Quizzes are course content: they stay after the term, but published ones are closed, and attempts are deleted.

## 10. AI assistant tiers

| Tier | What | Model | In the app |
|---|---|---|---|
| 1 | drafts from the course material: project ideas, sample proposal or writing guide, FAQ | local model only (trusted local connection) | API only (`/ai/drafts`) |
| 2 | drafts of KCs, prerequisites, check items, misconceptions from lecture notes; you accept them into the normal tables | local model only | API only |
| 3 | class insights: which topics students ask about, common misconceptions | none: labels and counts only, never question text | API only (`/insights`) |
| 4 | can the local model handle this course? generated test questions, answered by the local and the cloud model, scored, report per module | local and cloud; **course material goes to the cloud model only after you confirm** (`confirm_cloud`); not in a local-only course | API only (`/ai/evaluations`) |
| quizzes | question drafts (section 9) | local model only | **Quizzes** > **Draft with AI** |

Drafts are visible to students only after you accept them. No tier receives student data. Uploads are scanned
first (section 4).

**AI assistant** > **New draft** (tiers 1 and 2):
- **What to draft**: **Custom request** (the default) or one of the fixed kinds. A custom request is your own
  description of the draft, up to 1000 characters, for example "expand the material on one topic", "thesis or
  research topics", "a summary of this new paper and what it means for patients", "examples for a lecture" or
  "what to add to the course next". It is drafted as Markdown, like an FAQ.
- **Material to use**: **Whole course**, **One module** (with the course-level files), **Some modules** (only
  their files), **Some files** (only the files you tick), or **Upload a file** or **A web page**. An uploaded file or page (for example
  a new paper) is scanned like any upload and used for this draft only; it is deleted once the model has read
  it, unless you tick **Also add this file to the course material** (then it appears under **Materials** and
  students' answers can use it after the index is rebuilt).
- A draft is never shown to students until you accept it; a custom draft becomes a Markdown course material.
- **Model**: **Local model** (the default; the material stays on the course's server) or **Cloud model, for public
  material only**, which writes better drafts: tick the confirmation that the material is public (open course
  pages, published papers) and may go to the cloud model. Not offered in a local-only course. Student data is
  never part of a draft.

## 11. End-of-term survey

**End-of-term survey**: set **Survey window** (opening and closing time, usually the last week of term) and
save; set new times to change or close it. Status shows **open**, **closed** or **not set**. Students rate five
statements from 1 to 5, once, anonymously (answers carry no student ID or time; a separate record only notes
that the student answered). **Results** show the average per statement once at least 3 students answered ("Not
enough answers yet"); you never see single answers. There is no per-answer rating in the app: this survey is
the evaluation of the tutor.

## 12. End of term

First, under **Check the export first**, choose **Create an export** and **Download the export**: it holds what
the end of term will export, and nothing is deleted. Then **End of term** > **End the term…** Type the course
code to confirm, then **Export and delete**:
1. The server first writes the **export** (a ZIP): class summary, quiz results (`quizzes.json`), survey averages
   (`survey.json`) and, only where individual views are switched on and in mode B, the individual overviews you may see under exactly the same rules as the
   Students tab (agreed, not opted out, data after agreeing).
2. Then it deletes the course's student data: memberships, learner state, evidence, misconceptions, plans,
   conversations, request logs, usage counters, quiz attempts and the survey. Published quizzes are closed. The
   invitation code becomes void.
3. **Download the export** until it expires (72 hours by default, set by the administrator); after that it is
   deleted. **This cannot be undone**, so download it before leaving the page.
The course, modules, KCs, items, materials, settings, quizzes and instructors stay; accounts stay. A course
that will not run again can be archived after an ended term (**API only**: `POST .../archive`).

## 12a. Accounts from term to term

Who does what each term (instructor I, administrator A):

| When | Step | Who | Where |
|---|---|---|---|
| before the term | create instructor accounts (temporary password shown once) | A | **Administration** > instructor accounts |
| before the term | a new course, or import last term's content into a new course (section 12) | I | **My courses**, **Course content** > import |
| first week | import the class list (CSV with e-mail and name); existing accounts are added, new students join with the invitation code | I | **Members** > import, invitation code |
| during the term | a student forgot the password: **Reset password** (temporary, shown once) | I or A | **Members**, or **Administration** > **Student accounts** |
| during the term | a student dropped the course: remove the membership | I | **Members** > remove |
| end of term | export, then end the term (deletes the course's student data and memberships) | I | **End of term** |
| after the term | students who left the university: **Disable** (no more logins) or **Delete** (the account and all of its learning data in every course; cannot be undone) | A | **Administration** > **Student accounts** |
| after the term | instructors who left: **Disable** | A | **Administration** > instructor accounts |

Student accounts stay from term to term: next term's class list finds them by e-mail, and a student who keeps
the account keeps the same login. There is no university login yet (section 13).

## 13. Not in the app yet

Misconceptions, YAML import and export, AI tiers 1 to 4 (apart from quiz drafts), class insights, course
archiving, model connections and the invitation-code settings of the administrator are available through the
HTTP API ([design/api-v2.md](design/api-v2.md)); the app has no page for them. Ask an administrator for help
with those.
