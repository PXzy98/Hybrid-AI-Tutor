import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { COURSE, MODULES, ME_INSTRUCTOR, ME_STUDENT, mockApi, renderApp } from "./helpers";

// v5 V1: the deployment default. Individual views are off, so instructors see class statistics only.
const STATS_ONLY = { ...COURSE, visibility_mode: "A" as const, individual_view: false };
const instructor = (extra = {}) => ({
  "GET /auth/me": ME_INSTRUCTOR, "GET /courses": [{ ...STATS_ONLY, my_role: "instructor" }], "GET /courses/1/modules": MODULES,
  ...extra,
});

afterEach(() => vi.unstubAllGlobals());

describe("statistics-only instructor view", () => {
  it("has no Students section and opening its address shows the overview", async () => {
    mockApi(instructor({ "GET /courses/1/overview": { students: 6 } }));
    renderApp("/courses/1/students");
    const nav = await screen.findByRole("navigation", { name: /instructor/i });
    expect(nav).toHaveTextContent("Class overview");
    expect(nav).not.toHaveTextContent("Students");
    expect(screen.queryByRole("button", { name: /View progress/ })).not.toBeInTheDocument();
  });

  it("offers no visibility mode in the course settings", async () => {
    mockApi(instructor({
      "GET /courses/1/settings": { values: { visibility_mode: null, local_only: false, routing_preference: "default", show_routing_progress: true }, version: 1 },
      "GET /courses/1/model-endpoints": [],
    }));
    renderApp("/courses/1/settings");
    expect(await screen.findByText(/Instructors see class statistics only/)).toBeInTheDocument();
    expect(screen.queryByLabelText("What instructors see of students")).not.toBeInTheDocument();
  });

  it("shows quiz statistics without a per-student table", async () => {
    mockApi(instructor({
      "GET /courses/1/quizzes": [{ id: 4, title: "Quiz A", module_id: null, kind: "practice", status: "published", opens_at: null, closes_at: null,
        assigned_to: null, questions: [], attempts: 6, created_at: "", updated_at: "" }],
      "GET /courses/1/members": [],
      "GET /courses/1/quizzes/4/results": { quiz_id: 4, attempts: 6, sufficient_sample: true, min_group_size: 5, mean_score: 0.5, questions: [], students: [] },
    }));
    renderApp("/courses/1/quizzes");
    (await screen.findByRole("button", { name: "Results of Quiz A" })).click();
    expect(await screen.findByText("50%")).toBeInTheDocument();
    expect(screen.queryByText("No individual results are visible.")).not.toBeInTheDocument();
  });
});

describe("statistics-only student side", () => {
  it("shows no learning plan and no sharing choice", async () => {
    mockApi({
      "GET /auth/me": ME_STUDENT, "GET /courses": [STATS_ONLY], "GET /courses/1/modules": MODULES, "GET /courses/1/conversations": [],
      "GET /courses/1/me/profile": { personalized: true, modules: [], plan: null,
        visibility: { mode: "A", acknowledged: false, opted_out: false, visible_to_instructor: false, visible_since: null } },
    });
    renderApp("/courses/1/progress");
    expect(await screen.findByText("Your instructor cannot see your progress")).toBeInTheDocument();
    expect(screen.queryByText("Learning plan")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "I understand and agree" })).not.toBeInTheDocument();
  });
});
