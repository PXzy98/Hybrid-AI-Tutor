import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ME_INSTRUCTOR, instructorRoutes, mockApi, renderApp } from "./helpers";

afterEach(() => vi.unstubAllGlobals());

const MONDAYS = ["2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26", "2026-11-02", "2026-11-09"];
const weeks = [...MONDAYS.map((week_start) => ({ week_start, questions: null, students: null })),
  { week_start: "2026-11-16", questions: 42, students: 6 }];

describe("class statistics (V2)", () => {
  it("shows the use of the tutor and hides small groups", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/statistics": {
        min_group: 5, students_enrolled: 8, active_students: 6, active_students_7d: 6, questions_total: 120, questions_7d: 42,
        local_share: 0.75, weeks,
        modules: [{ module_id: null, title: "", questions: null }, { module_id: 10, title: "Ohm's law", questions: 37 }],
        quizzes: [{ quiz_id: 4, title: "Week 1 check", attempts: 6, mean_score: 0.6 }, { quiz_id: 5, title: "Week 2 check", attempts: 2, mean_score: null }],
      },
      "GET /courses/1/insights": { min_group: 5, suppressed: true, kc_question_counts: [], misconception_counts: [] },
    }));
    renderApp("/courses/1/overview");
    const card = await screen.findByLabelText("Use of the tutor");
    expect(await within(card).findByText("75%")).toBeInTheDocument();
    expect(within(card).getByText("42 questions, 6 students")).toBeInTheDocument();
    expect(within(card).getByText("37")).toBeInTheDocument();
    const quiz2 = within(card).getByText("Week 2 check").closest("tr")!;
    expect(within(quiz2).getByText("hidden")).toBeInTheDocument();
    expect(within(card).getByText("60%")).toBeInTheDocument();
  });

  it("shows the admin the counts of every course", async () => {
    mockApi({
      "GET /auth/me": { ...ME_INSTRUCTOR, system_role: "admin" }, "GET /courses": [],
      "GET /admin/statistics": { min_group: 5, students_enrolled: 30, active_students_7d: 12, questions_total: 300, questions_7d: 80,
        courses: [{ course_id: 1, code: "ECE 1000", title: "Fictional Circuits", status: "active", students_enrolled: 25, active_students_7d: 12, questions_total: 300, questions_7d: 80 },
                  { course_id: 2, code: "BIO 1000", title: "Fictional Biology", status: "archived", students_enrolled: 5, active_students_7d: 0, questions_total: null, questions_7d: null }] },
      "GET /admin/instructors": [], "GET /admin/settings": { values: {}, version: 1, apply_state: "applied" }, "GET /admin/model-endpoints": [],
    });
    renderApp("/admin");
    const table = await screen.findByRole("table", { name: "Use per course" });
    const bio = within(table).getByText("BIO 1000").closest("tr")!;
    expect(within(bio).getAllByText("hidden")).toHaveLength(2);
    expect(within(bio).getByText("archived")).toBeInTheDocument();
    expect(within(within(table).getByText("ECE 1000").closest("tr")!).getByText("300")).toBeInTheDocument();
  });
});
