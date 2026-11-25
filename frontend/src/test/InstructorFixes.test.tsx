import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { instructorRoutes, mockApi, reply, renderApp } from "./helpers";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

// V22: instructor-side findings of the browser test of 2026-11-21 (B9 to B18, B25). Fictional texts only.
const at = (day: string) => `2026-11-${day}T15:00:00Z`;
const note = (id: number, title: string, day: string, extra: Record<string, unknown> = {}) =>
  ({ id, title, body: "", pinned: false, created_at: at(day), updated_at: at(day), ...extra });
const mcq = (stem: string, options: string[]) => ({ kind: "mcq", kc: null, stem, options, answer: 0, explanation: "", sources: [], reviewed: true });
const quiz = (id: number, updated_at: string, extra: Record<string, unknown> = {}) => ({
  id, title: "Week 2", module_id: null, kind: "practice", status: "draft", opens_at: null, closes_at: null, assigned_to: null,
  questions: [], attempts: 0, created_at: updated_at, updated_at, ...extra });

describe("announcements (B9, B11, B12)", () => {
  it("shows the privacy refusal in French, naming the types only", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/announcements": [note(2, "Midterm review", "18")],
      "PATCH /courses/1/announcements/2": () => reply({ detail: "the privacy scan found student data: STUDENT_ID", code: "invalid" }, 422),
    }));
    renderApp("/courses/1/announcements", "fr");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Modifier Midterm review" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Texte"), "x");
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("L’analyse de confidentialité a trouvé des données d’étudiants (STUDENT_ID).");
  });

  it("marks the title as required, says why Save is disabled and counts characters near the limit", async () => {
    mockApi(instructorRoutes({ "GET /courses/1/announcements": [] }));
    renderApp("/courses/1/announcements");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "New announcement" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("Title")).toBeRequired();
    expect(within(dialog).getByLabelText("Title")).toHaveAttribute("aria-required", "true");
    const save = within(dialog).getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    expect(within(dialog).getByText("Fill in the title.")).toBeInTheDocument();
    expect(save).toHaveAccessibleDescription("Fill in the title.");
    await user.type(within(dialog).getByLabelText("Title"), "Exam");
    expect(within(dialog).queryByText("Fill in the title.")).not.toBeInTheDocument();
    expect(save).toBeEnabled();
    expect(within(dialog).queryByText(/characters/)).not.toBeInTheDocument();
    await user.paste("x".repeat(160));
    expect(within(dialog).getByText("164 / 200 characters")).toBeInTheDocument();
  });

  it("keeps the focus on the pin button of the item after the list is reordered", async () => {
    let rows = [note(2, "Midterm review", "18"), note(1, "Deadline moved", "05")];
    mockApi(instructorRoutes({
      "GET /courses/1/announcements": () => rows,
      "PATCH /courses/1/announcements/1": () => { rows = [{ ...rows[1], pinned: true }, rows[0]]; return rows[0]; },
    }));
    renderApp("/courses/1/announcements");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Pin Deadline moved" }));
    const unpin = await screen.findByRole("button", { name: "Unpin Deadline moved" });
    await waitFor(() => expect(unpin).toHaveFocus());
  });
});

describe("quizzes (B10, B12, B13)", () => {
  it("names the question when two options are the same, before anything is sent", async () => {
    const calls = mockApi(instructorRoutes({ "GET /courses/1/quizzes": [], "GET /courses/1/members": [], "GET /courses/1/kcs": [] }));
    renderApp("/courses/1/quizzes");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "New quiz" }));
    await user.type(screen.getByLabelText("Title"), "Week 2");
    await user.click(screen.getByRole("button", { name: "Add question" }));
    await user.type(screen.getByLabelText("Question"), "Unit of current?");
    await user.type(screen.getByLabelText("Option 1"), "Ampere");
    await user.type(screen.getByLabelText("Option 2"), "ampere ");
    await user.type(screen.getByLabelText("Option 3"), "Ampere");
    await user.click(screen.getByRole("button", { name: "Save quiz" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Question 1: two options are the same.");
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("does not show the pydantic prefix of a validation error", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/quizzes": [quiz(4, at("01"), { questions: [mcq("Unit of current?", ["Ampere", "Volt"])] })],
      "GET /courses/1/members": [], "GET /courses/1/kcs": [],
      "PATCH /courses/1/quizzes/4": () => reply({ detail: [{ type: "value_error", loc: ["body", "questions", 0], msg: "Value error, options must differ" }] }, 422),
    }));
    renderApp("/courses/1/quizzes");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Edit Week 2" }));
    await user.click(await screen.findByRole("button", { name: "Save quiz" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Two options of a question are the same.");
    expect(alert).not.toHaveTextContent("Value error");
  });

  it("says Saved after the first save of a new quiz, even when the server writes the time differently", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/quizzes": () => [quiz(8, "2026-11-21T10:00:00.123456")], "GET /courses/1/members": [], "GET /courses/1/kcs": [],
      "POST /courses/1/quizzes": () => reply(quiz(8, "2026-11-21T10:00:00.123456+00:00"), 201),
    }));
    renderApp("/courses/1/quizzes");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "New quiz" }));
    await user.type(screen.getByLabelText("Title"), "Week 2");
    await user.click(screen.getByRole("button", { name: "Save quiz" }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("moves the focus to New quiz after a quiz is deleted", async () => {
    let rows = [quiz(4, at("01"))];
    mockApi(instructorRoutes({
      "GET /courses/1/quizzes": () => rows, "DELETE /courses/1/quizzes/4": () => { rows = []; return reply(undefined, 204); },
    }));
    renderApp("/courses/1/quizzes");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Delete Week 2" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Delete quiz" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "New quiz" })).toHaveFocus());
  });
});

describe("class overview (B14 to B16)", () => {
  const summary = { topic: "t", min_group: 5, suppressed: false, students: 8,
    kcs: [{ kc_id: 1, name: "Ohm's law", counts: { basic: 0, intermediate: null, advanced: 6, mastered: 2 } }],
    misconceptions: [], misconceptions_hidden: 0 };

  it("shows a dash for nobody, hidden for a small group, and no extra hidden column", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/class-summary": summary,
      "GET /courses/1/statistics": { min_group: 5, students_enrolled: 8, active_students: 6, active_students_7d: 6, questions_total: 1, questions_7d: 1, local_share: 1, weeks: [], modules: [], quizzes: [] },
      "GET /courses/1/insights": { min_group: 5, suppressed: true, kc_question_counts: [], misconception_counts: [] },
      "GET /courses/1/weak-topics": { min_group: 5, topics: [] },
    }));
    renderApp("/courses/1/overview");
    const row = (await screen.findByRole("cell", { name: "Ohm's law" })).closest("tr")!;
    const cells = within(row).getAllByRole("cell").map((c) => c.textContent);
    expect(cells.slice(0, 5)).toEqual(["Ohm's law", "—", "hidden", "6", "2"]);
    expect(cells[5]).toBe("");  // the bar column: no second "hidden"
    expect(screen.getByText(/not the list|This is not the list/)).toBeInTheDocument();
    expect(screen.getAllByText("Students per level")).toHaveLength(1);
  });
});

describe("settings and end of term (B17)", () => {
  it("links End of term to the next-term form, which stays disabled until code and term are filled", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/settings": { values: { visibility_mode: "A", local_only: false, routing_preference: "default", show_routing_progress: true }, version: 1 },
      "GET /courses/1/model-endpoints": [],
    }));
    renderApp("/courses/1/endterm");
    const link = await screen.findByRole("link", { name: "Go to Start next term's course" });
    expect(link).toHaveAttribute("href", "/courses/1/settings#next-term");
  });

  it("explains why Create the new course is disabled", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/settings": { values: { visibility_mode: "A", local_only: false, routing_preference: "default", show_routing_progress: true }, version: 1 },
      "GET /courses/1/model-endpoints": [],
    }));
    renderApp("/courses/1/settings");
    const button = await screen.findByRole("button", { name: "Create the new course" });
    expect(button).toBeDisabled();
    expect(screen.getByText("Fill in the course code and the term.")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.type(document.getElementById("nt-code") as HTMLElement, "ECE 1000 W");
    await user.type(document.getElementById("nt-term") as HTMLElement, "Winter");
    expect(button).toBeEnabled();
  });
});

describe("login (B18)", () => {
  it("marks required fields and has a show-password toggle that keeps the autocomplete", async () => {
    mockApi({ "GET /auth/me": reply({ detail: "not logged in", code: "forbidden" }, 401) });
    renderApp("/login");
    const password = await screen.findByLabelText("Password");
    expect(password).toBeRequired();
    expect(password).toHaveAttribute("type", "password");
    expect(password).toHaveAttribute("autocomplete", "current-password");
    const toggle = screen.getByRole("button", { name: "Show password" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await userEvent.setup().click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(password).toHaveAttribute("type", "text");
    expect(password).toHaveAttribute("autocomplete", "current-password");
    expect(screen.getByLabelText("Username or e-mail")).toBeRequired();
  });
});

describe("content editors (B11, B25)", () => {
  const KC = { id: 5, module_id: 10, code: "K1", name: "Resistance", definition: "Opposition to current.", difficulty: "basic", status: "active" };
  const ITEM = { id: 8, kc_id: 5, code: "K1-q1", level: "basic", stem: "What is resistance measured in, and which instrument is used to read it on a bench?", answer: "B", explanation: "",
    status: "active", options: { A: { text: "Volt" }, B: { text: "Ohm" }, C: { text: "Watt" }, D: { text: "Ampere" } } };
  const routes = () => instructorRoutes({ "GET /courses/1/kcs": [KC], "GET /courses/1/check-items": [ITEM], "GET /courses/1/misconceptions": [] });

  it("uses a KC sentence without a correct answer, and puts the start of the question in the item button names", async () => {
    mockApi(routes());
    renderApp("/courses/1/content");
    const user = userEvent.setup();
    expect(await screen.findByRole("button", { name: "Edit K1-q1: What is resistance measured in, and which instrument is used…" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Retire K1-q1: What is resistance/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Edit Resistance" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Change the wording only: the code, the module, the level/)).toBeInTheDocument();
    expect(dialog).not.toHaveTextContent("correct answer");
    await user.clear(within(dialog).getByLabelText("Name"));
    expect(within(dialog).getByRole("button", { name: "Save" })).toBeDisabled();
    expect(within(dialog).getByText("Fill in the name.")).toBeInTheDocument();
    expect(within(dialog).getByLabelText("Name")).toHaveAttribute("aria-required", "true");
  });
});

describe("quiz saved note across time zones (retest B13)", () => {
  it("treats the same instant in UTC and in the database's zone as the same save", async () => {
    const { sameTime } = await import("@/pages/instructor/Quizzes");
    expect(sameTime("2026-11-21T22:13:17.389800Z", "2026-11-21T17:13:17.389800-05:00")).toBe(true);
    expect(sameTime("2026-11-21T22:13:17.389800", "2026-11-21T22:13:17.389800+00:00")).toBe(true);
    expect(sameTime("2026-11-21T22:13:17Z", "2026-11-21T22:13:18Z")).toBe(false);
  });
});
