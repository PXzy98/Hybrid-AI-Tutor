# Accessibility self-check (task T11)

Scope: the v2 frontend (`frontend/`), checked against WCAG 2.1 level AA. Date: 2026-11-13. Renaming is a separate,
open part of T11.

## How it was checked

| Method | What it covers |
|---|---|
| Code review of every page and shared component | Keyboard operation, headings, landmarks, labels, live regions, icons |
| `frontend/src/test/Accessibility.test.tsx` (vitest, `vitest-axe` with axe-core) | No serious or critical axe violation on: login (also with an error), course picker, student chat, my progress, instructor students, materials, quizzes (student and instructor), the end-of-term dialog. Also checks one `h1` on the login and chat pages, the skip link, dialog name and focus return, and arrow keys in tabs. A canary test proves the checker finds a missing label. |
| Contrast calculation on the theme tokens (`frontend/src/index.css`) | Text 4.5:1, UI boundaries 3:1, light and dark. The tokens are `oklch`; each pair was converted to sRGB and the WCAG ratio computed with a short script. |
| Layout reasoning | Reflow at 320 px and zoom to 200%, see below. jsdom has no layout, so this is not automated. |

Not done: a test with a real screen reader (NVDA, VoiceOver) and an automated colour-contrast run in a browser. See
"Known gaps".

## Results

### Keyboard
- Every control is a native `button`, `a`, `input`, `select` or `textarea`, or a Radix primitive, so Tab, Shift+Tab,
  Enter and Space work. No click-only handlers on non-interactive elements.
- Focus is visible: shadcn components use `focus-visible:ring-2` with the `--ring` token (3.6:1 light, 6.1:1 dark
  against the page); sidebar buttons and links have the same ring; native checkboxes, radios, file inputs and
  selects keep the browser outline.
- Dialogs (new course, end of term, material delete, data delete, cloud confirmation) are Radix `Dialog`: focus is
  trapped, Escape closes, focus returns to the button that opened it (tested for the end-of-term dialog).
- Tabs are Radix `Tabs`: arrow keys move between tabs (tested), the tab panel is reachable with Tab.
- Added a "Skip to the main content" link as the first focusable element; `main` has `id="main"` and is a focus
  target.

### Screen reader
- Landmarks: `header`, `aside` (named "Courses, modules and conversations"), `nav` (courses, modules,
  conversations, each named), `main`, and the footer note.
- Headings: one `h1` per page (the page, or the course title on a dashboard). Each dashboard tab has a visually
  hidden `h2` with the tab name. Card titles are announced as level 3 headings (`role="heading" aria-level=3`).
  The sidebar group labels are no longer headings.
- Forms: every field has a visible `label` (or an `aria-label` where the label is the context, for example module
  titles in the course editor). Login, join and password errors are `role="alert"` and referenced from the fields
  with `aria-describedby` (and `aria-invalid`).
- Live regions: the conversation is `aria-live="polite"`; the routing steps panel is `aria-live="off"` so the
  progress updates are not announced one by one; status messages (saved, imported, plan saved, answers
  submitted) are `role="status"`; errors are `role="alert"`.
- Icons are `aria-hidden` when next to text; icon-only buttons have an `aria-label`.
- The local/cloud label on an answer is text plus an icon (not colour alone); its hint is in `title`. Bands
  (basic, intermediate, advanced, mastered) are always written out.
- The page language is set on `<html lang>` and follows the language switch.

### Contrast (WCAG AA)
Computed from the theme tokens. All text pairs pass; the lowest is primary text on the page background in light
mode (5.25:1).

| Pair | Light | Dark |
|---|---|---|
| foreground on background | 17.0 | 16.8 |
| muted foreground on background / card / muted | 7.1 / 7.4 / 6.8 | 8.2 / 7.3 / 6.1 |
| primary foreground on primary (buttons) | 5.25 | 7.6 |
| primary on background (links, focus text) | 5.25 | 8.0 |
| accent foreground on accent | 11.5 | 11.1 |
| destructive on background | 5.2 | 6.5 |
| focus ring on background (needs 3:1) | 3.6 | 6.1 |
| form control border on card (needs 3:1) | 3.9 | 4.6 |

Fixed: the form control border (`--input`) was 1.3:1 in light mode and 1.7:1 in dark mode, below the 3:1 needed
for the boundary of a control; it is now 3.9:1 and 4.6:1. Decorative card borders stay light (not required).
Coloured badges and alerts use `-900` text on `-50` backgrounds in light mode and `-100` on `-950` in dark mode;
these are Tailwind pairs well above 4.5:1 (checked by value, not by script).

### Zoom and reflow
- Sizes use `rem`, so browser zoom and text size settings scale the layout.
- At 320 px the sidebar stacks above the content (`flex-col`, `md:flex-row`), the header wraps, tab lists wrap
  (`flex-wrap`), grids collapse to one column (`sm:` and `lg:` breakpoints), wide tables sit in an
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
