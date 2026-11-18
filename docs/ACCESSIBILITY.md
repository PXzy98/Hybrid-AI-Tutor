# Accessibility self-check (task T11)

Scope: the v2 frontend (`frontend/`), checked against WCAG 2.1 level AA. Date: 2026-11-13. Renaming (to PACT) was
the other part of T11 (#101).

## How it was checked

| Method | What it covers |
|---|---|
| Code review of every page and shared component | Keyboard operation, headings, landmarks, labels, live regions, icons |
| `frontend/src/test/Accessibility.test.tsx` (vitest, `vitest-axe` with axe-core) | No serious or critical axe violation on: login (also with an error), course picker, student chat, my progress, instructor students, materials, quizzes (student and instructor), the end-of-term dialog. Also checks one `h1` on the login and chat pages, the skip link, dialog name and focus return, the named section navigation with `aria-current="page"` and Tab order, and that the chat stays mounted when another section is open. A canary test proves the checker finds a missing label. |
| Contrast calculation on the theme tokens (`frontend/src/index.css`) | Text 4.5:1, UI boundaries 3:1, light and dark. The tokens are `oklch`; `npm run check:contrast` (`frontend/scripts/contrast.mjs`) converts each pair to sRGB, prints the WCAG ratios and fails when a pair is under its minimum. |
| Layout reasoning | Reflow at 320 px and zoom to 200%, see below. jsdom has no layout, so this is not automated. |

Not done: a test with a real screen reader (NVDA, VoiceOver) and an automated colour-contrast run in a browser. See
"Known gaps".

## Results

### Keyboard
- Every control is a native `button`, `a`, `input`, `select` or `textarea`, or a Radix primitive, so Tab, Shift+Tab,
  Enter and Space work. No click-only handlers on non-interactive elements.
- Focus is visible: shadcn components use `focus-visible:ring-2` with the `--ring` token (3.8:1 light, 7.0:1 dark
  against the page; form fields also turn their border to `--ring` with a 3 px ring); sidebar buttons and links have the same ring; native checkboxes, radios, file inputs and
  selects keep the browser outline.
- Dialogs (new course, end of term, material delete, data delete, cloud confirmation) are Radix `Dialog`: focus is
  trapped, Escape closes, focus returns to the button that opened it (tested for the end-of-term dialog). A student's detail on the
  instructor's Students page opens in a sheet (a Radix dialog from the right, named after the student) with the same
  behaviour; tested, including that one open sends exactly one overview request.
- The level-by-knowledge-component table on the class overview stays the accessible data; the stacked bar next to
  it (from `md` up) is an image with a sentence as its name, and a row with a suppressed count has no bar.
- Course sections are links in a named `nav` in the sidebar; the current one has `aria-current="page"` (tested).
  Inner tabs (AI assistant) are Radix `Tabs`: arrow keys move between them.
- The account menu (language, theme, password, log out) is a Radix dropdown menu: Enter or Space opens it, arrow
  keys move, Escape closes and returns focus. On small screens the sidebar is a Radix dialog (sheet) with the same
  focus behaviour; the top-bar button that opens it and the desktop hide / show button have an `aria-label` and a
  tooltip.
- Added a "Skip to the main content" link as the first focusable element; `main` has `id="main"` and is a focus
  target.

### Screen reader
- Landmarks: `aside` (named "Courses, modules and conversations"), `nav` (courses, course sections named
  "Student dashboard" or "Instructor dashboard", modules, conversations, each named), `header` (top bar), `main`,
  and the disclaimer note.
- Headings: one `h1` per page (the page, or the course code and title in the top bar on a course page). Each
  course section is a `section` labelled by a visually hidden `h2` with the section name. Card titles are announced as level 3 headings (`role="heading" aria-level=3`).
  The sidebar group labels are no longer headings.
- Forms: every field has a visible `label` (or an `aria-label` where the label is the context, for example module
  titles in the course editor). Login, join and password errors are `role="alert"` and referenced from the fields
  with `aria-describedby` (and `aria-invalid`).
- Live regions: the conversation is `aria-live="polite"`; the routing steps panel is `aria-live="off"` so the
  progress updates are not announced one by one; status messages (saved, imported, plan saved, answers
  submitted) are `role="status"`; errors are `role="alert"`.
- Icons are `aria-hidden` when next to text; icon-only buttons have an `aria-label`.
- The local/cloud label on an answer is text plus an icon (not colour alone); it is a button whose hint opens as a
  tooltip on hover and on keyboard focus. The chat's icon-only buttons (send, stop, copy, jump to the latest
  message) have an `aria-label` and a tooltip; "The tutor is thinking…" is visually hidden text in a `role="status"`.
  The page follows new text only while the reader is at the end of the conversation. Bands
  (basic, intermediate, advanced, mastered) are always written out.
- The page language is set on `<html lang>` and follows the language switch.

### Contrast (WCAG AA)
Computed from the theme tokens by `npm run check:contrast`, which fails on any pair below its minimum. Surfaces are
neutral (white and charcoal); teal is the only brand colour; status colours (`success`, `warning`, `info`,
`destructive`) are text colours that pass on the page, on cards and on their own `-soft` background. The lowest
text pair is primary on the sidebar in light mode (5.1:1).

| Pair | Light | Dark |
|---|---|---|
| foreground on background / sidebar / card / accent | 18.1 / 16.9 / 18.1 / 15.9 | 16.5 / 17.1 / 15.5 / 13.4 |
| muted foreground on background / sidebar / card / muted / accent | 6.5 / 6.1 / 6.5 / 5.9 / 5.7 | 7.7 / 8.0 / 7.2 / 6.5 / 6.3 |
| primary foreground on primary (buttons) | 5.25 | 8.5 |
| primary on background / card / sidebar (links) | 5.5 / 5.5 / 5.1 | 8.7 / 8.1 / 9.0 |
| primary-soft foreground on primary-soft (selected item, bands) | 11.5 | 10.9 |
| destructive on background / card / destructive-soft | 5.4 / 5.4 / 4.9 | 6.6 / 6.2 / 5.6 |
| destructive-soft foreground on destructive-soft (error alerts) | 6.7 | 8.2 |
| success on success-soft / card | 6.3 / 7.1 | 8.9 / 10.1 |
| warning on warning-soft / card | 6.4 / 7.0 | 9.2 / 10.6 |
| info on info-soft / card | 6.7 / 7.4 | 8.6 / 9.7 |
| focus ring on background / sidebar (needs 3:1) | 3.8 / 3.5 | 7.0 / 7.2 |
| form control border on background / card (needs 3:1) | 3.9 / 3.9 | 3.9 / 3.7 |

Badges and alerts use these token pairs (no Tailwind palette colour is left in `src/`). Bands use one hue with
rising weight (muted, primary-soft, primary-soft with a border, primary) and always write the band name.
Decorative card borders stay light (not required).

### Zoom and reflow
- Sizes use `rem`, so browser zoom and text size settings scale the layout.
- Below `md` the sidebar is a sheet opened from the top bar and the content is full width; the top-bar title
  truncates, inner tab lists wrap (`flex-wrap`), grids collapse to one column (`sm:` and `lg:` breakpoints), wide tables sit in an
  `overflow-x-auto` wrapper (the table scrolls, not the page), and `main` allows long words and codes to wrap
  (`overflow-wrap:anywhere`, `min-w-0`). Dialogs are `max-w-[calc(100%-2rem)]`.
- 200% zoom is equivalent to a 640 px wide viewport at the same layout; the `sm:` layout applies.

## Known gaps
- No manual run with a screen reader or in a real browser at 320 px and 200% zoom; do this before the beta.
- Automated colour contrast (axe `color-contrast`) is off in jsdom; the numbers above come from the token
  calculation, not from rendered pixels. Text drawn on tinted badges was not measured by script.
- The routing steps panel and the draft editor for knowledge components, check items and misconceptions (a JSON
  textarea) are usable with a keyboard but not pleasant with a screen reader.
- Streamed tokens are announced as a whole answer when it finishes; incremental announcements are not used on
  purpose.
- The French strings are machine-assisted and need review (T10), including the accessible names used in tests.
- Renaming of the product (rest of T11) is open.
