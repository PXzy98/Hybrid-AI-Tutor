import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { instructorRoutes, mockApi, renderApp, studentRoutes } from "./helpers";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const question = (stem: string, reviewed: boolean) => ({
  kind: "mcq", kc: null, stem, options: ["Ohm", "Volt", "Watt"], answer: 0, explanation: "Because.", sources: [], reviewed,
});

describe("student quiz", () => {
  it("answers once and shows the result with explanations", async () => {
    let attempt: unknown = null;
    const calls = mockApi(studentRoutes({
      "GET /courses/1/quizzes": () => [{
        id: 3, title: "Week 1 check", module_id: null, kind: "practice", open: attempt === null, opens_at: null, closes_at: null,
        questions: attempt ? [] : [
          { kind: "mcq", stem: "Unit of resistance?", options: ["Ohm", "Volt"] },
          { kind: "true_false", stem: "Current is measured in amperes.", options: ["True", "False"] },
        ],
        attempt,
      }],
      "POST /courses/1/quizzes/3/attempt": () => {
        attempt = { score: 1, total: 2, submitted_at: "2026-11-10T00:00:00Z", results: [
          { correct: true, chosen: 0, answer: 0, explanation: "Resistance is measured in ohms." },
          { correct: false, chosen: 1, answer: 0, explanation: "Amperes measure current." },
        ] };
        return attempt;
      },
    }));
    renderApp("/courses/1/quizzes");
    const user = userEvent.setup();
    const submit = await screen.findByRole("button", { name: "Submit answers" });
    expect(submit).toBeDisabled();
    await user.click(screen.getByLabelText("Ohm"));
    await user.click(screen.getByLabelText("False"));
    await user.click(submit);
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("Score: 1 / 2");
    expect(within(status).getByText("Resistance is measured in ohms.")).toBeInTheDocument();
    expect(within(status).getByText("Amperes measure current.")).toBeInTheDocument();
    expect(within(status).getByText("Unit of resistance?")).toBeInTheDocument();
    const post = calls.find((c) => c.path === "/courses/1/quizzes/3/attempt")!;
    expect(post.body).toEqual({ answers: [0, 1] });
    expect(post.headers["X-CSRF-Token"]).toBe("test-token");
    await waitFor(() => expect(screen.queryByRole("button", { name: "Submit answers" })).not.toBeInTheDocument());
  });
});

describe("instructor quiz review gate", () => {
  it("keeps publishing disabled until the AI-drafted questions are saved as reviewed", async () => {
    let quiz = { id: 4, title: "Draft quiz", module_id: null, kind: "practice", status: "draft", opens_at: null, closes_at: null, assigned_to: null,
      questions: [question("Typed by hand", true)], attempts: 0, created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z" };
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/quizzes": () => [quiz],
      "GET /courses/1/members": [], "GET /courses/1/kcs": [],
      "POST /courses/1/quizzes/4/drafts": () => ({ job_id: 9 }),
      "GET /courses/1/jobs/9": () => {
        quiz = { ...quiz, questions: [...quiz.questions, question("Written by the model", false)], updated_at: "2026-11-02T00:00:00Z" };
        return { id: 9, kind: "quiz.draft", status: "done", progress: 1, error: null, created_at: "", started_at: null, finished_at: null };
      },
      "PATCH /courses/1/quizzes/4": (c: { body: { questions?: unknown[]; status?: string } }) => {
        if (c.body.questions) quiz = { ...quiz, questions: quiz.questions.map((q) => ({ ...q, reviewed: true })), updated_at: "2026-11-03T00:00:00Z" };
        if (c.body.status) quiz = { ...quiz, status: c.body.status };
        return quiz;
      },
    }));
    renderApp("/courses/1/quizzes");
    const user = userEvent.setup();
    const publish = await screen.findByRole("button", { name: "Publish Draft quiz" });
    expect(publish).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Edit Draft quiz" }));
    await user.click(await screen.findByRole("button", { name: "Draft with AI" }));
    expect(calls.find((c) => c.path === "/courses/1/quizzes/4/drafts")!.body).toEqual({ count: 5, kinds: ["mcq", "true_false"] });
    expect(await screen.findByText("AI draft, not reviewed")).toBeInTheDocument();
    expect(screen.getByText(/must be checked and saved/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Back to the list" }));
    expect(await screen.findByText("1 not reviewed")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Publish Draft quiz" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Edit Draft quiz" }));
    await user.click(await screen.findByRole("button", { name: "Save quiz" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH" && (c.body as { questions?: unknown }).questions)).toBe(true));
    await waitFor(() => expect(screen.queryByText("AI draft, not reviewed")).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Back to the list" }));
    const ready = await screen.findByRole("button", { name: "Publish Draft quiz" });
    expect(ready).toBeEnabled();
    await user.click(ready);
    await waitFor(() => expect(calls.some((c) => (c.body as { status?: string } | undefined)?.status === "published")).toBe(true));
  });

  it("says there are not enough answers when the sample is too small", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/quizzes": [{ id: 4, title: "Quiz A", module_id: null, kind: "final", status: "published", opens_at: null, closes_at: null,
        assigned_to: null, questions: [question("Q", true)], attempts: 2, created_at: "", updated_at: "" }],
      "GET /courses/1/members": [],
      "GET /courses/1/quizzes/4/results": { quiz_id: 4, attempts: 2, sufficient_sample: false, min_group_size: 5, questions: [], students: [] },
    }));
    renderApp("/courses/1/quizzes");
    await userEvent.setup().click(await screen.findByRole("button", { name: "Results of Quiz A" }));
    expect(await screen.findByText(/Not enough answers yet/)).toHaveTextContent("at least 5");
    expect(screen.getByText("No individual results are visible.")).toBeInTheDocument();
  });
});

describe("end-of-term survey", () => {
  it("lets a student answer the five ratings once while it is open", async () => {
    let answered = false;
    const calls = mockApi(studentRoutes({
      "GET /courses/1/survey": () => ({ opens_at: "2026-11-01T00:00:00Z", closes_at: "2026-12-01T00:00:00Z", open: true, answered }),
      "POST /courses/1/survey/responses": () => { answered = true; return { opens_at: null, closes_at: null, open: true, answered: true }; },
    }));
    renderApp("/courses/1/survey");
    const user = userEvent.setup();
    const submit = await screen.findByRole("button", { name: "Submit survey" });
    expect(submit).toBeDisabled();
    for (const group of screen.getAllByRole("radiogroup")) await user.click(within(group).getByLabelText("4"));
    expect(submit).toBeEnabled();
    await user.click(submit);
    expect(await screen.findByText(/anonymous answers were saved/)).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/courses/1/survey/responses")!.body).toEqual({
      helpfulness: 4, material_relevance: 4, clarity: 4, source_confidence: 4, learning_effect: 4,
    });
  });

  it("shows nothing to answer when the survey is closed", async () => {
    mockApi(studentRoutes({ "GET /courses/1/survey": { opens_at: null, closes_at: null, open: false, answered: false } }));
    renderApp("/courses/1/survey");
    expect(await screen.findByText("The survey is not open now.")).toBeInTheDocument();
  });

  it("lets the instructor set the window and hides averages until the sample is large enough", async () => {
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/survey": { opens_at: null, closes_at: null, open: false, results: { responses: 2, min_group_size: 5, sufficient_sample: false } },
      "PUT /courses/1/survey": { opens_at: "2026-12-01T10:00:00Z", closes_at: "2026-12-08T10:00:00Z", open: false, results: { responses: 2, min_group_size: 5, sufficient_sample: false } },
    }));
    renderApp("/courses/1/survey");
    const user = userEvent.setup();
    expect(await screen.findByText(/Not enough answers yet/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Opens"), "2026-12-01T10:00");
    await user.type(screen.getByLabelText("Closes"), "2026-12-08T10:00");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    const body = calls.find((c) => c.method === "PUT")!.body as { opens_at: string; closes_at: string };
    expect(new Date(body.closes_at).getTime()).toBeGreaterThan(new Date(body.opens_at).getTime());
  });
});
