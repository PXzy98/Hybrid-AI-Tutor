import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { afterEach, describe, expect, it, vi } from "vitest";

import { instructorRoutes, mockApi, reply, renderApp, studentRoutes } from "./helpers";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

/** axe-core on the rendered page; colour contrast needs a real layout engine and is checked by script (docs/ACCESSIBILITY.md). */
async function violations(container: HTMLElement) {
  const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(" ")).join(" | ")})`);
}

const members = [
  { id: 2, role: "student", status: "active", account_id: 3, username: "ana", display_name: "Ana Example", email: "ana@example.test", created_at: "2026-09-02T00:00:00Z", student_id: "stu-ana", visible_to_instructor: true },
  { id: 3, role: "student", status: "active", account_id: 4, username: "ben", display_name: "Ben Example", email: "ben@example.test", created_at: "2026-09-02T00:00:00Z", student_id: "stu-ben", visible_to_instructor: false },
];

it("the checker finds a real problem (an unlabelled field and an image without text)", async () => {
  const host = document.createElement("div");
  host.innerHTML = '<input type="text"><img src="x.png">';
  document.body.appendChild(host);
  expect((await violations(host)).length).toBeGreaterThan(0);
  host.remove();
});

describe("axe: no serious or critical violations", () => {
  it("login", async () => {
    mockApi({ "GET /auth/me": () => reply({ detail: "no", code: "forbidden" }, 401) });
    const { container } = renderApp("/login");
    await screen.findByRole("button", { name: "Log in" });
    expect(await violations(container)).toEqual([]);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("login with an error is linked to the fields", async () => {
    mockApi({ "GET /auth/me": () => reply({ detail: "no", code: "forbidden" }, 401),
      "POST /auth/login": () => reply({ detail: "Wrong username or password.", code: "invalid" }, 400) });
    const { container } = renderApp("/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Username or e-mail"), "x");
    await user.type(screen.getByLabelText("Password"), "y");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    const alert = await screen.findByRole("alert");
    expect(screen.getByLabelText("Password")).toHaveAttribute("aria-describedby", alert.id);
    expect(await violations(container)).toEqual([]);
  });

  it("course picker", async () => {
    mockApi(studentRoutes());
    const { container } = renderApp("/courses");
    await screen.findByRole("heading", { level: 1, name: "My courses" });
    expect(await violations(container)).toEqual([]);
  });

  it("student chat", async () => {
    mockApi(studentRoutes());
    const { container } = renderApp("/courses/1/chat");
    await screen.findByLabelText("Your question");
    expect(await violations(container)).toEqual([]);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Skip to the main content" })).toHaveAttribute("href", "#main");
  });

  it("my progress", async () => {
    mockApi(studentRoutes({
      "GET /courses/1/me/profile": { personalized: true, preferences: null, plan: null,
        modules: [{ module_id: 10, code: "M1", title: "Ohm's law", kcs: [{ kc_id: "K1", name: "Resistance", band: "basic" }], misconceptions: [] }],
        visibility: { mode: "B", acknowledged: false, opted_out: false, visible_to_instructor: false } },
    }));
    const { container } = renderApp("/courses/1/progress");
    await screen.findByText("Resistance");
    expect(await violations(container)).toEqual([]);
  });

  it("instructor students", async () => {
    mockApi(instructorRoutes({ "GET /courses/1/members": members }));
    const { container } = renderApp("/courses/1/students");
    await screen.findByText("Ben Example");
    expect(await violations(container)).toEqual([]);
  });

  it("materials", async () => {
    mockApi(instructorRoutes({ "GET /courses/1/materials": { index_version: 1, rebuild_job_id: null,
      materials: [{ id: 1, module_id: null, filename: "syllabus.pdf", size_bytes: 2048, scan_status: "clean", uploaded_at: "2026-11-01T00:00:00Z" }] } }));
    const { container } = renderApp("/courses/1/materials");
    await screen.findByText("syllabus.pdf");
    expect(await violations(container)).toEqual([]);
  });

  it("quizzes (student and instructor)", async () => {
    mockApi(studentRoutes({ "GET /courses/1/quizzes": [{ id: 3, title: "Week 1 check", module_id: null, kind: "practice", open: true, opens_at: null, closes_at: null,
      questions: [{ kind: "mcq", stem: "Unit of resistance?", options: ["Ohm", "Volt"] }], attempt: null }] }));
    const student = renderApp("/courses/1/quizzes");
    await screen.findByText("Unit of resistance?");
    expect(await violations(student.container)).toEqual([]);
    student.unmount();

    mockApi(instructorRoutes({ "GET /courses/1/quizzes": [{ id: 4, title: "Quiz A", module_id: null, kind: "practice", status: "draft", opens_at: null, closes_at: null,
      assigned_to: null, questions: [{ kind: "mcq", kc: null, stem: "Q", options: ["a", "b"], answer: 0, explanation: "", sources: [], reviewed: false }], attempts: 0, created_at: "", updated_at: "" }] }));
    const instructor = renderApp("/courses/1/quizzes");
    await screen.findByText("Quiz A");
    expect(await violations(instructor.container)).toEqual([]);
  });

  it("system administration", async () => {
    mockApi({ "GET /auth/me": { account_id: 9, username: "ada", email: null, display_name: "Ada Admin", system_role: "admin", must_change_password: false, memberships: [] },
      "GET /courses": [],
      "GET /admin/instructors": [{ account_id: 2, username: "ida@example.test", email: "ida@example.test", display_name: "Ida Instructor", role: "instructor", active: true, must_change_password: false, last_login_at: null }],
      "GET /admin/settings": { values: { weak_evidence: true, level_basic_below: 0.4, level_advanced_above: 0.8, level_hysteresis: 0.05, default_routing_method: "lr", enabled_course_types: ["ece"] }, version: 1, apply_state: "applied" },
      "GET /admin/model-endpoints": [{ id: 4, course_id: null, name: "Lab server", kind: "ollama", base_url: "http://localhost:11434", model: "fictional", trust: "trusted_local", api_key_last4: null, last_test_ok_at: null }] });
    const { container } = renderApp("/admin");
    await screen.findByText("Lab server");
    expect(await violations(container)).toEqual([]);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Edit Lab server" }));
    const dialog = await screen.findByRole("dialog");
    expect(await violations(dialog)).toEqual([]);
  });

  it("course content and settings with the new cards", async () => {
    mockApi(instructorRoutes({ "GET /courses/1/kcs": [], "GET /courses/1/check-items": [],
      "GET /courses/1/misconceptions": [{ id: 7, kc_id: 5, code: "MC1", statement: "Wrong idea", correction: "Right idea", status: "active" }] }));
    const content = renderApp("/courses/1/content");
    await screen.findByText("Wrong idea");
    expect(await violations(content.container)).toEqual([]);
    content.unmount();
    mockApi(instructorRoutes({ "GET /courses/1/settings": { values: {}, version: 1 }, "GET /courses/1/model-endpoints": [] }));
    const settings = renderApp("/courses/1/settings");
    await screen.findByRole("button", { name: "Archive course" });
    expect(await violations(settings.container)).toEqual([]);
  });

  it("the end of term dialog is labelled and returns focus", async () => {
    mockApi(instructorRoutes());
    renderApp("/courses/1/endterm");
    const user = userEvent.setup();
    const trigger = await screen.findByRole("button", { name: "End the term…" });
    await user.click(trigger);
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveAccessibleName("Delete the student data of this course?");
    expect(await violations(dialog)).toEqual([]);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });

  it("tabs move with the arrow keys", async () => {
    mockApi(instructorRoutes());
    renderApp("/courses/1/overview");
    const user = userEvent.setup();
    const first = await screen.findByRole("tab", { name: "Class overview" });
    first.focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Students" })).toHaveFocus();
  });
});
