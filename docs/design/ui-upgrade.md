# UI upgrade plan (frontend v2 → "mature AI tool" look)

Status: done, phases U1 to U5 merged (#81 to #85, 2026-11-15). Written 2026-11-13 against `origin/main` at
`58cf667`; kept as the record of the design decisions.
Audience: a coding agent (or a teammate) who implements this without the author present.

Read [AGENTS.md](../../AGENTS.md) and sections 2, 7.4 and 8 of
[v4-implementation-guide.md](../v4-implementation-guide.md) first. Where this file and the guide disagree, the
guide wins; say so in the PR instead of following this file.

---

## 1. Goal and non-goals

**Goal.** The frontend works and is accessible, but it looks like a default component-library admin page: a
header bar, a pill tab strip that wraps to two rows, bordered chat bubbles, a loud amber footer, a navy dark
mode. Make it look and feel like an established AI product (the family of Claude, ChatGPT, Linear, Vercel):
calm neutral surfaces, one restrained accent, a full-height app shell, a centred reading column for the chat,
a floating composer, quiet motion, and privacy status that is always visible but never noisy.

**Non-goals. Do not do any of these:**

- No backend, API, OpenAPI or `schema.d.ts` change. This is a pure `frontend/` change (plus two docs).
- No new feature and no removed feature. Every control that exists today exists afterwards, with the same
  accessible name.
- No per-answer rating and no "more detail / shorter" buttons under answers (guide section 9 decided this).
- No permission logic in the frontend (rule 8): keep showing exactly what the API returns.
- No framework move (no Next.js), no state library, no CSS-in-JS.
- No web fonts or scripts from a CDN at runtime. The product is deployed locally and is privacy-first: every
  asset is bundled.
- No change of wording in `i18n/en.ts` / `i18n/fr.ts` for existing keys, except the keys listed in section 9.

## 2. What exists today (verified facts)

| Area | File | State |
|---|---|---|
| Stack | `frontend/package.json` | React 19, Vite 5, Tailwind 4 (`@tailwindcss/vite`), React Router 6, TanStack Query 5, Radix (collapsible, dialog, label, slot, tabs), cva, lucide-react, react-markdown + remark-gfm + remark-math + rehype-katex |
| Tokens | `frontend/src/index.css` | shadcn tokens in `oklch`, teal primary, slate-blue neutrals (hue 265), `.dark` class. Also six legacy `@utility` rules (`btn`, `btn-primary`, `btn-secondary`, `btn-link`, `input`, `card`, `label`) that nothing uses any more |
| Shell | `src/components/AppShell.tsx` | Top header (brand, language, theme, name, log out); left `aside` `md:w-64` with three `nav`s (courses, modules, conversations); `main` `max-w-6xl`; amber disclaimer `footer role="note"`. The page scrolls as a whole |
| Course page | `src/pages/CourseDashboard.tsx` | `h1` (course code + title) and Radix `Tabs`: 5 tabs for students, 10 for instructors. Chat is `forceMount`ed so a running answer survives a tab change |
| Chat | `src/pages/student/Chat.tsx` | Student bubble in primary colour; tutor answer as a bordered card `max-w-[90%]`; "Thinking…" as plain text; routing steps in a `Collapsible`; sources as chips; `CheckCard` under the answer; composer is a `sticky bottom-0` card with a cloud notice inside |
| Primitives | `src/components/ui/*` | alert, badge, button, card, collapsible, dialog, input, label, select (native), table, tabs, textarea |
| Shared | `src/components/common.tsx`, `Band.tsx`, `Markdown.tsx`, `RoutingProgress.tsx`, `CheckCard.tsx` | `ErrorNote`, `SectionTitle`, `ThemeToggle`; band badges; Markdown without code highlighting |
| Loading / empty | all pages | `<p className="text-muted-foreground">{t("app.loading")}</p>` in 14 files; empty states are one grey sentence |
| Hard-coded colours | pages and `ui/alert`, `ui/badge`, `Band`, `CheckCard` | `emerald-*`, `amber-*`, `sky-*`, `rose-*`, `violet-*`, `red-*` with `dark:` pairs, about 60 uses; `LanguageSwitch` in `src/i18n/index.tsx` still uses `slate-*` and `bg-white` (wrong in dark mode) |
| Tests | `src/test/*.test.tsx` | Vitest + Testing Library; `Accessibility.test.tsx` runs axe on nine screens and asserts one `h1`, the skip link, dialog focus return, and **arrow-key movement between tabs** |
| Accessibility record | `docs/ACCESSIBILITY.md` | WCAG 2.1 AA self-check with a contrast table computed from the tokens |

## 3. Design direction

Five principles. When a detail is not specified below, decide by these.

1. **Neutral first, one accent.** Surfaces are white / near-white (light) and charcoal (dark) with almost no
   hue. Teal stays the only brand colour and is used for: the primary button, links, the focus ring, the
   selected navigation item, the brand mark. Nothing else is teal.
2. **Flat, bordered, quiet.** Hairline borders separate things; shadows only on floating layers (composer,
   popover, dialog, sheet). No gradients, no glass, no coloured page backgrounds.
3. **Content gets a reading column.** Chat and forms sit in a centred column (`max-w-3xl`, about 48rem); data
   tables may use `max-w-6xl`. Text line length stays under about 80 characters.
4. **Status is text plus icon in a semantic colour**, never colour alone (already true; keep it).
5. **Motion explains, then gets out of the way.** 120–200 ms, ease-out, opacity and small transforms only,
   all disabled under `prefers-reduced-motion: reduce`.

### 3.1 Tokens (replace the `:root` and `.dark` blocks of `index.css`)

All pairs below were converted from `oklch` to sRGB and checked against WCAG 2.1 (ratios in section 3.2).
Do not change a value without re-running the check (section 10.3).

```css
:root {
  --radius: 0.625rem;
  --background: oklch(1 0 0);
  --foreground: oklch(0.2 0.01 260);
  --sidebar: oklch(0.975 0.003 250);
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.2 0.01 260);
  --popover: oklch(1 0 0);
  --popover-foreground: oklch(0.2 0.01 260);
  --primary: oklch(0.51 0.09 186);
  --primary-foreground: oklch(0.985 0 0);
  --primary-soft: oklch(0.95 0.03 190);
  --primary-soft-foreground: oklch(0.3 0.06 190);
  --secondary: oklch(0.965 0.003 250);
  --secondary-foreground: oklch(0.2 0.01 260);
  --muted: oklch(0.965 0.003 250);
  --muted-foreground: oklch(0.48 0.012 260);
  --accent: oklch(0.955 0.004 250);
  --accent-foreground: oklch(0.2 0.01 260);
  --destructive: oklch(0.55 0.22 27);
  --destructive-soft: oklch(0.965 0.02 25);
  --destructive-soft-foreground: oklch(0.47 0.18 27);
  --success: oklch(0.45 0.11 155);
  --success-soft: oklch(0.96 0.03 155);
  --success-border: oklch(0.87 0.06 155);
  --warning: oklch(0.47 0.1 70);
  --warning-soft: oklch(0.97 0.035 85);
  --warning-border: oklch(0.87 0.08 85);
  --info: oklch(0.45 0.1 245);
  --info-soft: oklch(0.965 0.02 245);
  --info-border: oklch(0.88 0.045 245);
  --border: oklch(0.915 0.004 250);
  --input: oklch(0.6 0.01 255);
  --ring: oklch(0.6 0.1 186);
  --shadow-float: 0 1px 2px oklch(0 0 0 / 0.04), 0 8px 24px oklch(0 0 0 / 0.08);
}

.dark {
  --background: oklch(0.17 0.004 260);
  --foreground: oklch(0.95 0.003 250);
  --sidebar: oklch(0.145 0.004 260);
  --card: oklch(0.205 0.005 260);
  --card-foreground: oklch(0.95 0.003 250);
  --popover: oklch(0.23 0.005 260);
  --popover-foreground: oklch(0.95 0.003 250);
  --primary: oklch(0.74 0.1 186);
  --primary-foreground: oklch(0.18 0.02 200);
  --primary-soft: oklch(0.28 0.04 190);
  --primary-soft-foreground: oklch(0.9 0.05 186);
  --secondary: oklch(0.25 0.005 260);
  --secondary-foreground: oklch(0.95 0.003 250);
  --muted: oklch(0.25 0.005 260);
  --muted-foreground: oklch(0.72 0.01 255);
  --accent: oklch(0.26 0.006 260);
  --accent-foreground: oklch(0.95 0.003 250);
  --destructive: oklch(0.7 0.19 22);
  --destructive-soft: oklch(0.25 0.05 25);
  --destructive-soft-foreground: oklch(0.8 0.12 22);
  --success: oklch(0.8 0.13 155);
  --success-soft: oklch(0.25 0.04 155);
  --success-border: oklch(0.38 0.07 155);
  --warning: oklch(0.83 0.12 85);
  --warning-soft: oklch(0.26 0.04 80);
  --warning-border: oklch(0.4 0.07 80);
  --info: oklch(0.8 0.09 245);
  --info-soft: oklch(0.25 0.035 245);
  --info-border: oklch(0.38 0.06 245);
  --border: oklch(0.29 0.006 260);
  --input: oklch(0.55 0.01 260);
  --ring: oklch(0.68 0.1 186);
  --shadow-float: 0 1px 2px oklch(0 0 0 / 0.3), 0 8px 24px oklch(0 0 0 / 0.4);
}
```

Changes of meaning compared with today, which matter when restyling:

- `--accent` is now a **neutral hover / pressed surface**. The teal tint it used to be is `--primary-soft`.
  Every existing `bg-accent` that marks a *selected* item becomes `bg-primary-soft text-primary-soft-foreground`;
  every `hover:bg-accent` stays.
- `--background` is pure white / charcoal; the tinted surface is `--sidebar`.
- New families `success`, `warning`, `info`, `destructive-soft`. `--success`, `--warning`, `--info` are **text
  colours** that are safe on both the page and their own `-soft` background.

Add every new variable to the `@theme inline` block (`--color-sidebar: var(--sidebar);` and so on for
`primary-soft`, `primary-soft-foreground`, `destructive-soft`, `destructive-soft-foreground`, `success`,
`success-soft`, `success-border`, `warning`, `warning-soft`, `warning-border`, `info`, `info-soft`,
`info-border`) and `--shadow-float: var(--shadow-float);` so `shadow-float` is a utility.

Delete the seven legacy `@utility` rules at the end of `index.css`. Remove `class="bg-slate-50"` from
`index.html` (the body colour comes from the base layer).

### 3.2 Contrast of these tokens (WCAG ratio, light / dark)

| Pair | Light | Dark | Needs |
|---|---|---|---|
| foreground on background / sidebar / card / accent | 18.1 / 16.9 / 18.1 / 15.9 | 16.5 / 17.1 / 15.5 / 13.4 | 4.5 |
| muted-foreground on background / sidebar / card / muted / accent | 6.5 / 6.1 / 6.5 / 5.9 / 5.7 | 7.7 / 8.0 / 7.2 / 6.5 / 6.3 | 4.5 |
| primary-foreground on primary | 5.25 | 8.5 | 4.5 |
| primary on background / card / sidebar | 5.5 / 5.5 / 5.1 | 8.7 / 8.1 / 9.0 | 4.5 |
| primary-soft-foreground on primary-soft | 11.5 | 10.9 | 4.5 |
| destructive on background / card | 5.4 / 5.4 | 6.6 / 6.2 | 4.5 |
| destructive-soft-foreground on destructive-soft | 6.7 | 8.2 | 4.5 |
| success on success-soft / card | 6.3 / 7.1 | 8.9 / 10.1 | 4.5 |
| warning on warning-soft / card | 6.4 / 7.0 | 9.2 / 10.6 | 4.5 |
| info on info-soft / card | 6.7 / 7.4 | 8.6 / 9.7 | 4.5 |
| ring on background / sidebar | 3.8 / 3.5 | 7.0 / 7.2 | 3.0 |
| input (control border) on background / card | 3.9 / 3.9 | 3.9 / 3.7 | 3.0 |

White text on `--destructive` (the destructive button) is unchanged from today.

### 3.3 Typography

- Font: **Inter variable**, self-hosted through the `@fontsource-variable/inter` package (imported once in
  `main.tsx`; Vite bundles the files). Set `--font-sans: "Inter Variable", ui-sans-serif, system-ui, sans-serif`
  in `@theme`. Code stays on the system monospace stack. Turn on `font-feature-settings: "cv11", "ss01"` and
  `-webkit-font-smoothing: antialiased` on `body`.
- Scale (use only these):

| Use | Classes |
|---|---|
| Page title (`h1`) | `text-xl font-semibold tracking-tight` |
| Section title (`h2`) | `text-base font-semibold` |
| Card title (`h3` role) | `text-sm font-semibold` |
| Body, chat answer | `text-[0.9375rem] leading-7` (15 px) |
| UI text, tables, forms | `text-sm` |
| Meta, captions, group labels | `text-xs text-muted-foreground` |
| Large number on a stat card | `text-2xl font-semibold tabular-nums` |

- Sidebar group labels: sentence case, `text-xs font-medium text-muted-foreground`. Drop
  `uppercase tracking-wide`.

### 3.4 Shape, spacing, elevation, motion

- Radius: controls `rounded-md`; cards and panels `rounded-xl`; composer `rounded-2xl`; badges `rounded-full`.
- Cards lose `shadow-sm` (border only). `shadow-float` is reserved for composer, dropdown, dialog, sheet, toast.
- Spacing rhythm: 4 / 8 / 12 / 16 / 24 / 32 px. Page padding `px-4 sm:px-6`, section gap `space-y-6`, inside a
  card `space-y-4`.
- Control height: 36 px (`h-9`) default, 32 px (`h-8`) small. Touch targets in the sidebar at least 36 px high.
- Motion utilities, defined once in `index.css`:
  - `animate-in-fade`: opacity 0 → 1, 150 ms;
  - `animate-in-up`: opacity 0 → 1 and `translateY(4px)` → 0, 180 ms (new chat messages, toasts);
  - `animate-shimmer`: for skeletons;
  - `animate-caret`: blinking streaming caret.
  Wrap all of them in `@media (prefers-reduced-motion: no-preference)`.

## 4. Dependencies

Add only these. Take the current stable version at install time and commit `package-lock.json`.

| Package | Why |
|---|---|
| `@fontsource-variable/inter` | self-hosted font |
| `@radix-ui/react-dropdown-menu` | user menu in the sidebar (language, theme, change password, log out) |
| `@radix-ui/react-tooltip` | labels for icon-only buttons (collapse sidebar, copy, send) |
| `sonner` | toasts for "copied" and background results (named in guide 7.4) |

Everything else is built from what is already installed: the mobile drawer is a `Sheet` on
`@radix-ui/react-dialog`; skeletons, the stacked band bar and the step timeline are plain CSS.

Deliberately **not** added in this plan: Recharts, TanStack Table, Motion, AI Elements, assistant-ui,
react-hook-form. The current pages do not need them, and each is a large surface to keep accessible.
Code highlighting is phase U6 and optional (section 8).

## 5. Layout: the app shell

Replace the header + sidebar + footer layout with a full-height shell. `AppShell.tsx` is rewritten; split the
sidebar into `src/components/shell/Sidebar.tsx`, `UserMenu.tsx`, `CourseNav.tsx`, `NewCourseDialog.tsx`.

```
┌──────────────┬──────────────────────────────────────────────────────┐
│ ◈ ScholarMind  «│  ELG 5902  Privacy-aware tutors   [Student]      │  top bar, 48 px, h1 lives here
│              │──────────────────────────────────────────────────────│
│ ELG 5902   ▾ │                                                      │
│              │                                                      │
│ ✎ New chat   │              scrolling content area                  │
│ ▢ Chat       │        (centred column, max-w-3xl or 6xl)            │
│ ◔ My progress│                                                      │
│ ✓ Quizzes    │                                                      │
│ ✦ Personalize│                                                      │
│ ☰ Survey     │                                                      │
│              │                                                      │
│ Modules      │                                                      │
│  Whole course│                                                      │
│  1 Ohm's law │              ┌────────────────────────────┐          │
│ Today        │              │ composer (chat only)       │          │
│  12 Nov · 4… │              └────────────────────────────┘          │
│──────────────│   The tutor can be wrong. Check important answers.   │  role="note", muted, 28 px
│ (Z) Zhenyan ▾│                                                      │
└──────────────┴──────────────────────────────────────────────────────┘
   264 px, bg-sidebar
```

Rules:

- Root: `h-dvh flex overflow-hidden`. Only the content area scrolls (`overflow-y-auto`), so the sidebar, the top
  bar and the composer never move.
- **Sidebar** (`aside`, keep `aria-label={t("nav.sidebar")}`), `w-66` (264 px), `bg-sidebar`, `border-r`:
  1. Brand row: mark + `t("app.name")` linking to `/courses`, and a collapse button (icon `PanelLeft`,
     `aria-label`, tooltip, `aria-expanded`). Collapsed state hides the sidebar completely on desktop and shows
     an expand button in the top bar. Persist it in `localStorage` under `tutor.sidebar` (same try/catch pattern
     as `tutor.theme`; an interface preference, nothing about the user).
  2. Course switcher: a native `<select>` styled like the `Select` primitive when there are courses, followed by
     "Join a course" and (non-students) "New course" as small ghost buttons. Keep the `nav` with
     `aria-label={t("nav.courses")}`. On `/courses` (no course open) show the course list as links instead.
  3. **Course sections** (new; replaces the tab strip, see section 6): one `nav`,
     `aria-label={t(student ? "dash.student" : "dash.instructor")}`, a `NavLink` per section with an icon,
     `aria-current="page"` on the active one. Active style `bg-primary-soft text-primary-soft-foreground
     font-medium`; hover `bg-accent`.
  4. Students only: "New chat" as the first, prominent item; then Modules (scope picker, same behaviour as
     today's `CourseNav.open`); then Conversations grouped by date ("Today", "Yesterday", "Earlier") from
     `last_at`. Each row keeps today's label (date and number of turns): the API stores no question text and
     no titles, so **do not invent conversation titles**.
  5. Footer, pinned to the bottom: user menu trigger (initials avatar + display name). The dropdown contains the
     language choice, the theme choice (light / dark / system), "Change password" (link to `/change-password`)
     and "Log out". `LanguageSwitch` and `ThemeToggle` keep their exported names and accessible names but render
     inside the menu; the standalone `LanguageSwitch` on Login and Join stays and is restyled with tokens.
- **Top bar** (`header`), 48 px, `border-b`, `bg-background`: sidebar toggle (when collapsed or on mobile), the
  page `h1` (course code in `font-semibold`, title in `text-muted-foreground`, truncated), role badge, archived
  badge. No other controls.
- **Disclaimer**: the same string `t("app.disclaimer")` in one `role="note"` element, as a
  `text-xs text-muted-foreground text-center` strip under the content area. No amber.
- **Skip link**: unchanged (first focusable element, `href="#main"`).
- **Mobile (`< md`)**: the sidebar is a `Sheet` (Radix dialog sliding from the left, labelled with
  `t("nav.sidebar")`), opened from the top-bar button and closed on navigation. Content is full width.
- Guard loading state in `App.tsx`: a centred brand mark with a spinner instead of grey text; the unreachable
  state uses the `EmptyState` component (section 7) with a retry button that calls `refetch`.

## 6. Course sections instead of tabs

`CourseDashboard.tsx` keeps the route `/courses/:courseId/:tab?` and the `tabs` arrays (ids and i18n keys stay,
so every URL and deep link keeps working). It stops rendering Radix `Tabs`; the sidebar renders the links.

- Export the two section lists (id, label key, icon) from one module, for example
  `src/pages/sections.ts`, used by both the sidebar and the dashboard.
- Student sections and icons: chat `MessageSquare`, progress `ChartNoAxesColumn`, quizzes `ListChecks`,
  start `SlidersHorizontal`, survey `ClipboardList`.
- Instructor sections, shown in three labelled groups (new i18n keys, section 9):
  - **Class**: overview `LayoutDashboard`, students `Users`;
  - **Teaching**: content `BookOpen`, materials `FileStack`, quizzes `ListChecks`, ai `Sparkles`;
  - **Course**: members `UserPlus`, settings `Settings`, survey `ClipboardList`, endterm `CalendarX`.
- The dashboard renders the active section inside `<section aria-labelledby>` with the existing visually hidden
  `h2` (tab name). Unknown `:tab` falls back to the first section, as today.
- **Chat must stay mounted** while a student visits another section (a running answer and the live messages
  live in component state). Render `<Chat>` always for students and hide it with the `hidden` attribute when
  another section is active; render the other sections only when active.
- Tests to change in the same PR: in `Accessibility.test.tsx` replace "tabs move with the arrow keys" with a
  test that the section nav exists, that the active link has `aria-current="page"`, and that Tab reaches the
  next link. Any test that finds a section with `getByRole("tab", …)` switches to `getByRole("link", …)` with
  the same name. No assertion may be deleted without a replacement.
- `ui/tabs.tsx` stays (the AI assistant page uses inner tabs). Restyle it as an underline tab bar:
  list `border-b gap-4 bg-transparent p-0`, trigger `border-b-2 border-transparent pb-2
  data-[state=active]:border-primary data-[state=active]:text-foreground`.

## 7. Components

### 7.1 Restyle existing primitives (`src/components/ui/`)

| File | Change |
|---|---|
| `button.tsx` | `outline`: `border bg-background hover:bg-accent`. Add `active:scale-[0.98]` and `transition` (colour and transform). Add size `icon-sm` (`size-8`). Add a `loading` prop that shows a `Loader2` spinner, sets `aria-busy` and disables the button; use it wherever a label is swapped for "Saving…" today (keep the swapped label too, tests read it) |
| `card.tsx` | remove `shadow-sm`; `rounded-xl border bg-card` |
| `input.tsx`, `textarea.tsx`, `select.tsx` | `bg-background`, remove `shadow-xs`, `focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/30`, `aria-invalid:border-destructive`. `select.tsx` stays a native select; add a chevron with `appearance-none` and a background icon |
| `badge.tsx` | `rounded-full`; variants `warning`, `success` move to the tokens (`border-warning-border bg-warning-soft text-warning`), add `info` and `destructive` the same way |
| `alert.tsx` | variants on tokens; optional leading icon slot (`Info`, `TriangleAlert`, `CircleAlert`), `aria-hidden` |
| `dialog.tsx` | overlay `bg-black/40 backdrop-blur-[2px]`; content `rounded-xl shadow-float animate-in-up`; add a close button (`X`, `aria-label={t("dialog.close")}`) |
| `table.tsx` | header row `bg-muted/50 text-xs font-medium`, cells `px-3 py-2.5`, the wrapper gets `rounded-lg border`; when a table is the only content of a `Card`, drop the card |

### 7.2 New shared components

| Component | File | Contract |
|---|---|---|
| `Sheet` | `ui/sheet.tsx` | Radix dialog, side `left`, width 18rem, same focus behaviour as `Dialog` |
| `DropdownMenu` | `ui/dropdown-menu.tsx` | shadcn pattern on `@radix-ui/react-dropdown-menu` |
| `Tooltip` | `ui/tooltip.tsx` | shadcn pattern; one `TooltipProvider` in `main.tsx` (`delayDuration` 300). A tooltip never replaces `aria-label` |
| `Skeleton` | `ui/skeleton.tsx` | `div` with `animate-shimmer bg-muted rounded-md`, `aria-hidden` |
| `Toaster` | `ui/sonner.tsx` | themed with the tokens, mounted once in `main.tsx`, `position="bottom-right"` |
| `PageHeader` | `common.tsx` | title (`h2`), description, right-aligned actions slot. Replaces the hand-written "title + intro + select" blocks in Overview, Students, Start, Materials, Members, Quizzes, Content, Settings, EndOfTerm. `SectionTitle` is removed in its favour |
| `Loading` | `common.tsx` | `<div role="status" aria-busy="true">` containing a visually hidden `t("app.loading")` and skeleton children. **Replaces all 14 `app.loading` paragraphs.** Keep the text in the DOM: tests and screen readers rely on it. Give it a `variant`: `list`, `table`, `cards`, `chat`, `form` |
| `EmptyState` | `common.tsx` | icon in a `size-10 rounded-full bg-muted` circle, title, one sentence, optional action. Replaces the grey one-line empty messages (no courses, no modules, no students, no quizzes, no materials, no drafts). The sentence is the existing i18n string; the title is new (section 9) |
| `StatCard` | `common.tsx` | label (`text-xs text-muted-foreground`), value (`text-2xl font-semibold tabular-nums`), optional icon. Used by Overview |
| `StatusText` | `common.tsx` | `role="status"` line with `Check` icon in `text-success`. Replaces every `text-emerald-700 dark:text-emerald-300` paragraph (10 uses) |
| `BandBar` | `components/BandBar.tsx` | one horizontal stacked bar for a row of band counts, widths in percent, each segment labelled by `title` and included in an `aria-label` sentence ("Basic 4, Intermediate 7, …"). Suppressed (`null`) counts are **not drawn and not estimated**: show the existing "hidden" text instead of a bar for that row |

### 7.3 Token migration of hard-coded colours

Replace every Tailwind palette class in `src/` (outside tests) with a token class. Mapping:

| Today | Becomes |
|---|---|
| `text-emerald-700 dark:text-emerald-300`, `border-emerald-500 bg-emerald-50 dark:bg-emerald-950` | `text-success`, `border-success-border bg-success-soft` |
| `amber-*` groups (alerts, warnings, footer, routing prototype note) | `text-warning`, `border-warning-border bg-warning-soft` |
| `sky-*` groups | `text-info`, `border-info-border bg-info-soft` |
| `rose-*`, `red-*` groups | `text-destructive`, `border-destructive/40 bg-destructive-soft text-destructive-soft-foreground` |
| `slate-*`, `bg-white` in `i18n/index.tsx` | `Select` primitive / token classes |
| `Band.tsx` sky / violet / emerald per band | one hue, rising weight: basic `bg-muted text-muted-foreground`, intermediate `bg-primary-soft text-primary-soft-foreground`, advanced `border-primary bg-primary-soft text-primary-soft-foreground font-semibold`, mastered `bg-primary text-primary-foreground`, not assessed `border-dashed text-muted-foreground`. The band name stays written out |

Done when `git grep -nE "(slate|gray|zinc|teal|emerald|amber|sky|rose|red|violet)-[0-9]" frontend/src -- ':!*test*'`
returns nothing.

## 8. Page by page

Each page keeps its data flow, its queries and its accessible names. Only presentation changes unless stated.

### 8.1 Login, Join, Change password

- Centred column `max-w-sm` on `bg-sidebar`, brand mark above the card, the card on `bg-card` with border, the
  language switch moved to the top-right corner of the page.
- Inputs 40 px high (`h-10`) on these three pages only. Submit button uses `loading`.
- Under the card: one muted line with the privacy promise that already exists in `login.intro` (do not write new
  claims).

### 8.2 Course picker

- `PageHeader` with the title; actions: "Join a course", and "New course" for non-students.
- Course cards: code as `text-sm font-semibold`, title below, a footer row with role, term and archived badges.
  Whole card is the link (as today) with `hover:border-foreground/20 hover:bg-accent/40` and a trailing
  `ArrowRight` that appears on hover and focus.
- Loading: three skeleton cards. Empty: `EmptyState` with the "Join a course" action.

### 8.3 Student chat (the page that defines the product)

Split `Chat.tsx` (269 lines) into `src/pages/student/chat/`: `Chat.tsx` (state, unchanged logic),
`MessageList.tsx`, `TutorMessage.tsx`, `Composer.tsx`, `RoutingPanel.tsx`, `Sources.tsx`, `EmptyChat.tsx`.
**Move code, do not rewrite the state machine**: `epoch` / `shown` handling, `hydrated`, the `ask` mutation and
`updateTrace` stay byte-for-byte where possible.

Layout: the chat fills the content area as a flex column: a scrolling message list and the composer pinned
below it. Both use the same centred column, `mx-auto w-full max-w-3xl px-4`.

- **Context row** at the top of the list (not sticky): scope badge (`Whole course` or the module title) and the
  level `Band`. The two banners (`VisibilityBanner`, "not personalized") stay above it, restyled by `Alert`.
- **Student message**: right-aligned, `max-w-[85%] rounded-2xl bg-secondary px-4 py-2.5`, foreground text. No
  primary colour (a screen of teal bubbles is what makes the page look dated).
- **Tutor message**: **no bubble, no border**. An `article` that takes the full column:
  1. header row: a 24 px brand mark, `t("chat.tutor")` (new key) in `text-sm font-medium`, then the route label;
  2. the Markdown body at the body size of 3.3;
  3. warnings as one `Alert variant="warning"` with a list (replace the "⚠" characters by the icon);
  4. sources;
  5. "Suggested next" line;
  6. the action row;
  7. `CheckCard`.
- **Route label** (local / cloud): keep the `Badge`, `data-route` attribute and texts. `local` →
  `success` variant with `ShieldCheck`; `cloud` → `info` variant with `Cloud` (cloud is a normal, permitted
  path, so it is not a warning colour). Replace `title` by a `Tooltip` with the same hint text and keep the hint
  reachable by keyboard (the badge becomes a `button type="button"` trigger).
- **Sources**: a row of compact cards `rounded-lg border bg-card px-2.5 py-1.5 text-xs` with a numbered square
  `[1]`, the title in `font-medium` and the source file below in muted text, at most 2 lines. Wrap, do not scroll
  sideways. The API returns no passage text today, so no hover preview; do not fake one.
- **Action row** under a finished tutor message: one ghost `icon-sm` button "Copy" (copies `reply.answer` as
  Markdown, then a toast `t("chat.copied")`). Nothing else: no rating, no regenerate, no style buttons.
- **Thinking state**: replace the "Thinking…" paragraph by the tutor header row plus three pulsing dots, with
  `t("chat.thinking")` kept as visually hidden text inside a `role="status"`.
- **Streaming**: while `partial` is shown, render it in the same tutor-message layout with a blinking caret
  (`animate-caret`) after the last block. When the result arrives the final message replaces it in place with
  no layout jump (same wrapper, same width).
- **Routing steps** (`RoutingPanel` + `RoutingProgress`): keep it collapsed by default, `aria-live="off"`, and
  keep every string. Trigger: a quiet pill above the answer, `rounded-full border px-2.5 py-1 text-xs`, with a
  spinner while running and a check when finished, the label, and the elapsed seconds. Content: a vertical
  timeline (a 1 px line with a dot per stage: hollow = pending, spinning = running, filled = completed, dash =
  skipped, red = failed), the stage name left and the duration right in `tabular-nums`. The status word stays
  in the text, so state is never colour-only.
- **Composer**: `rounded-2xl border bg-card shadow-float`, focus-within shows the ring on the whole box. Inside:
  the textarea (no own border, auto-grow from 1 to 8 rows, then scroll; implement with a `ref` and
  `scrollHeight`, no dependency), and a bottom row with the scope badge on the left and the send button on the
  right. Send button: round, `size-9`, primary, icon `ArrowUp`, visible text replaced by
  `aria-label={t("chat.send")}` **and** a tooltip. While an answer is running it becomes a "Stop" button
  (`Square` icon, `aria-label={t("chat.stop")}`) that calls `controller.current?.abort()`. The abort controller
  already exists; an aborted request must end quietly (no error bubble for an `AbortError`).
  Enter sends, Shift+Enter makes a new line (unchanged); do not send while an IME composition is active
  (`e.nativeEvent.isComposing`).
- **Cloud notice** (`CloudNotice`, rule T8): must stay visible **before** sending whenever
  `!course.local_only`. Move it out of the box to one muted line directly under the composer, with the `Cloud`
  icon, same strings, same `role="note"`. It must not be collapsible or dismissible.
- **Empty state** (`EmptyChat`): vertically centred in the list area: brand mark, `t("chat.emptyTitle")` (new)
  as a `text-xl font-semibold` line, the existing `chat.empty` sentence, then the three suggestions as cards
  in a `sm:grid-cols-3` grid (`rounded-xl border p-3 text-sm text-left hover:bg-accent`). Clicking one fills
  the composer and focuses it (today's behaviour: it does not send).
- **Scrolling**: stick to the bottom only when the reader is already near the bottom (within about 80 px);
  if they scrolled up, do not pull them down, and show a round "Jump to latest" button above the composer
  (`aria-label={t("chat.jump")}`). Keep the `scrollIntoView?.()` guard: jsdom has no such method.
- **History**: stored answers (`role: "history"`) use the tutor layout without the route label (the API does not
  return it for past turns). Loading a past conversation shows the `chat` skeleton.
- **`CheckCard`**: `rounded-xl border bg-card p-4` with a small "Quick check" header. Each option is a full-width
  selectable row (`rounded-lg border px-3 py-2.5`, the native radio kept and visible; selected row
  `border-primary bg-primary-soft`). After grading: the right option `border-success-border bg-success-soft`
  with a `Check` icon, the wrong choice `border-destructive/40 bg-destructive-soft` with an `X` icon. The
  result text and `role="status"` stay.

### 8.4 Student: My progress, Personalize, Quizzes, Survey

- **My progress**: `PageHeader`; left column: per module a card with the module title and each knowledge
  component as a row (name left, `Band` right, rows separated by hairlines); the "working on" block becomes an
  `Alert variant="info"` style panel. Right column: the visibility card first (it is the privacy control):
  a large status line with `Eye` / `EyeOff`, the status badge (`visible` → `info`, `hidden` → `success`), then
  the action. The delete-data card gets a `border-destructive/30` outline and stays last.
- **Personalize (Start)**: one column `max-w-2xl`. The three cards become three numbered steps with a visible
  step label ("1 Consent", "2 Preferences", "3 Short check") down the left edge; all on one page, nothing
  hidden behind "Next" (every part can be skipped and nothing may look mandatory). Radio options become
  selectable rows like in `CheckCard`. The save bar sticks to the bottom of the content area.
- **Quizzes / Survey**: `PageHeader`, question blocks as cards with selectable rows, a progress line
  "n of m answered" above the submit button. Result states use `StatusText` and the token colours.

### 8.5 Instructor pages

Shared: `PageHeader` with the module `Select` or the primary action in the actions slot; tables with the new
`Table` style; `Loading variant="table"`; `EmptyState` for empty lists; forms in `max-w-2xl` with
labels above fields and a single primary button per form.

- **Overview**: three `StatCard`s; "Class insights" as two ranked lists where each row has a thin proportional
  bar behind the count (width = count / max count); "Level by knowledge component" keeps the table (it is the
  accessible data) and adds a `BandBar` column on `md` and wider. Suppressed groups keep the `info` alert and
  show no chart at all.
- **Students**: the table stays. The detail view opens in a right-hand `Sheet` (`side="right"`,
  `max-w-xl`) instead of a card below the table, so the list stays in place; the sheet title is the student's
  name. Opening it still triggers exactly one overview request (each view is audited: do not prefetch, do not
  refetch on hover or focus).
- **Content, Materials, Members, Quizzes**: list on top, editor in a card below or a dialog as today. Material
  rows show a file icon, size and a scan status badge (`clean` → `success`, pending → `secondary`, infected or
  failed → `destructive`). The upload control becomes a dashed drop zone that still contains the native file
  input (keyboard and screen reader path unchanged).
- **AI assistant**: inner underline tabs (7.1). Draft cards show kind, status badge (`generating` with spinner,
  `draft` → `info`, `accepted` → `success`, `discarded` → `secondary`, `failed` → `destructive`) and the
  actions right-aligned. Generated text is rendered with `Markdown`.
- **Settings**: group the form into titled sections (course info, privacy and cloud, visibility mode,
  personalization, usage limits) inside one card each, with a sticky save bar showing "Unsaved changes" when the
  form is dirty. The 409 conflict keeps its current alert and reload action.
- **End of term**: a "danger zone" card with `border-destructive/30`; the export preview and download stay above
  the delete action; the confirmation dialog is unchanged in behaviour (its accessible name is tested).

### 8.6 Markdown

`Markdown.tsx`: replace the long arbitrary-variant class list by a `.markdown` block in `index.css` (headings,
paragraphs, lists, `blockquote`, `hr`, tables with a rounded border and header background, inline code
`rounded bg-muted px-1 py-0.5 text-[0.85em]`, `pre` `rounded-lg border bg-muted p-3 text-sm overflow-x-auto`,
KaTeX display blocks `overflow-x-auto`). Raw HTML stays disabled.

Optional, phase U6 only: a copy button on code blocks and syntax highlighting. Guide 7.4 names Shiki; it is
asynchronous and heavy for streamed text, so the suggestion is `rehype-highlight` with a small language set.
That is a deviation from 7.4: get the frontend owner's agreement in the PR before adding it.

## 9. Strings

New keys, added to **both** `i18n/en.ts` and `i18n/fr.ts` in the same PR (the `I18n.test.tsx` suite compares the
two). French needs review by the French reviewer named in guide task T10; mark the PR accordingly.

| Key | English |
|---|---|
| `nav.collapse` / `nav.expand` | Hide the sidebar / Show the sidebar |
| `nav.group.class` / `nav.group.teaching` / `nav.group.course` | Class / Teaching / Course |
| `nav.today` / `nav.yesterday` / `nav.earlier` | Today / Yesterday / Earlier |
| `nav.account` | Account menu |
| `nav.changePassword` | Change password |
| `theme.system` | Use the system setting |
| `dialog.close` | Close |
| `chat.tutor` | Tutor |
| `chat.emptyTitle` | What would you like to understand today? |
| `chat.copy` / `chat.copied` | Copy the answer / Copied |
| `chat.stop` | Stop the answer |
| `chat.jump` | Jump to the latest message |
| `empty.*.title` | one short title per `EmptyState` (for example `empty.courses.title`: No courses yet) |
| `form.unsaved` | Unsaved changes |

Do not rename or reword existing keys. Check with `git grep` that a key does not already exist before adding it.

## 10. Rules that hold in every phase

### 10.1 Privacy and product rules

- No question text, answer text or profile data in `localStorage`, `sessionStorage`, IndexedDB, the URL, the
  page title, `console.*` or any analytics call. Only `tutor.lang`, `tutor.theme` and `tutor.sidebar` are stored.
- No request to any third-party origin. No CDN font, no remote icon, no telemetry.
- The cloud notice, the local/cloud label on every answer, the visibility banner and the disclaimer stay
  visible in the places they are today (or the place this plan names).
- The frontend shows what the API returns: no client-side filtering that hides or reveals students, bands or
  counts; suppressed aggregates are never charted or estimated.

### 10.2 Accessibility (WCAG 2.1 AA, see `docs/ACCESSIBILITY.md`)

- One `h1` per page; hidden `h2` per section; card titles as level 3.
- Landmarks: `header`, `aside` (named), each `nav` named, `main#main` with `tabIndex={-1}`, the `role="note"`.
- Every icon-only button has an `aria-label`; icons next to text are `aria-hidden`.
- Focus ring visible on every interactive element on every surface (`bg-background`, `bg-sidebar`, `bg-card`).
- Dialogs and sheets trap focus, close on Escape, return focus to the trigger.
- Reflow at 320 px wide and at 200% zoom with no horizontal page scroll; sizes in `rem`.
- `prefers-reduced-motion` disables every animation in 3.4.
- Update `docs/ACCESSIBILITY.md` in the PR that changes what it describes (tokens and contrast table in U1,
  landmarks and section navigation in U2).

### 10.3 Checks before every PR

```
cd frontend
npm run build
npm test
git grep -nE "(slate|gray|zinc|teal|emerald|amber|sky|rose|red|violet)-[0-9]" src -- ':!*test*'   # from U1 on: empty
```

- Contrast: when a token changes, recompute the table in 3.2. Add `frontend/scripts/contrast.mjs` in U1
  (oklch → OKLab → linear sRGB → relative luminance → WCAG ratio, about 30 lines, no dependency) that prints the
  table and exits non-zero when a text pair is under 4.5 or a boundary pair under 3.0; wire it as
  `npm run check:contrast`.
- Manual pass in a real browser with the demo data (`docs/DEMO.md`): light and dark, 1440 px, 768 px, 375 px,
  keyboard only, as a student and as an instructor. Put before/after screenshots of the changed pages in the PR.
- Existing tests are the behaviour contract. A test may change only when the plan changes the markup it reads
  (tabs → links, loading text → hidden text inside `role="status"`); never weaken an assertion to make it pass.

## 11. Phases (one PR each, in this order)

Frontend is owned by T (guide section 5, `.github/CODEOWNERS`). Before starting, add these rows to guide
section 7.3a in a small docs PR and get the task IDs agreed; if someone other than the owner implements them,
follow guide 7.5 (own PR, for the owner's review). Branch names: `feature/u1-ui-tokens`, and so on.

| ID | Scope | Main files | Done when |
|---|---|---|---|
| U1 | Tokens, font, motion utilities, primitive restyle, token migration (7.3), contrast script. No layout change | `index.css`, `index.html`, `main.tsx`, `components/ui/*`, `Band.tsx`, `CheckCard.tsx`, `common.tsx`, `i18n/index.tsx`, colour classes in pages, `scripts/contrast.mjs`, `docs/ACCESSIBILITY.md` | checks in 10.3 pass; the grep is empty; no test changed |
| U2 | App shell and section navigation (sections 5 and 6): sidebar, user menu, top bar, mobile sheet, disclaimer strip, dashboard without the tab strip | `AppShell.tsx` → `components/shell/*`, `CourseDashboard.tsx`, `pages/sections.ts`, `ui/sheet.tsx`, `ui/dropdown-menu.tsx`, `ui/tooltip.tsx`, `App.tsx`, i18n, affected tests, `docs/ACCESSIBILITY.md`, `frontend/README.md` | all URLs work as before; chat survives a section change; axe tests pass on all nine screens |
| U3 | Student chat (8.3) and Markdown styles (8.6) | `pages/student/chat/*`, `Markdown.tsx`, `RoutingProgress.tsx`, `CheckCard.tsx`, `ui/sonner.tsx`, i18n, `Student.test.tsx` additions (stop button, copy, IME guard, no auto-scroll when scrolled up) | chat tests pass; streaming shows no layout jump; cloud notice visible before sending |
| U4 | Shared states and student pages: `PageHeader`, `Loading`, `EmptyState`, `StatusText`, `Skeleton`; Login, Join, Change password, Course picker, Progress, Start, Quizzes, Survey | `common.tsx`, `ui/skeleton.tsx`, the listed pages | no `app.loading` paragraph left outside `Loading` |
| U5 | Instructor pages (8.5): `StatCard`, `BandBar`, table style, student detail sheet, settings sections, material drop zone | `pages/instructor/*`, `components/BandBar.tsx` | instructor tests pass; one overview request per opened student (assert it in a test) |
| U6 | Optional polish: code block copy and highlighting (needs the owner's agreement), `Students` table sorting, print styles for the progress page | as agreed | as agreed |

Each of U1–U5 is shippable alone and leaves the app consistent. U3, U4 and U5 depend on U1 and U2 and are
independent of each other.

## 12. Definition of done for the whole upgrade

- A first-time visitor sees a product of the same visual family as current AI assistants: sidebar, quiet top
  bar, centred conversation, floating composer, no tab strip, no coloured footer.
- Light and dark mode both look intentional (dark is charcoal, not navy), with every pair in 3.2 passing.
- No hard-coded palette colour in `src/`; every colour is a token.
- Every loading state is a skeleton, every empty state has an icon, a title and (where there is one) an action.
- `npm run build`, `npm test` and `npm run check:contrast` pass; the axe suite covers the same nine screens.
- `docs/ACCESSIBILITY.md` and `frontend/README.md` describe the new shell.
- No backend file changed; no API call added; `schema.d.ts` untouched.

## 13. Decisions left to the frontend owner

These are choices this plan made that the owner may overrule before U1 starts. Defaults apply if nobody objects.

| Decision | Default in this plan | Alternative |
|---|---|---|
| Section navigation | sidebar links for both roles | keep horizontal tabs for students (5 fit on one row) |
| Brand colour | keep teal `oklch(0.51 0.09 186)` | pick a new brand colour together with the open renaming (T11) |
| Cloud answers label colour | `info` (blue) | keep `warning` (amber) as today |
| Send button | icon-only with `aria-label` and tooltip | keep the visible "Send" text |
| Chat component library | none; keep our own components | AI Elements or assistant-ui (guide 7.4), which would replace 8.3 |
| Code highlighting | off (U6) | `rehype-highlight` or Shiki |
