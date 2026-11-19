import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { instructorRoutes, mockApi, reply, renderApp } from "./helpers";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const draft = (over = {}) => ({
  id: 7, kind: "kcs", module_id: null, status: "draft", content: { items: [{ name: "Ohm's law", definition: "V = IR" }] },
  cited_sources: ["lecture1.pdf"], error: null, created_by: 2, created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z", ...over,
});

describe("AI drafts", () => {
  it("starts a draft, waits for the job, edits and accepts it into a module", async () => {
    let status = "generating";
    let polls = 0;
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/ai/drafts": () => [{ id: 7, kind: "kcs", module_id: null, status, created_at: "", updated_at: "" }],
      "POST /courses/1/ai/drafts": () => reply(draft({ status: "generating", content: {}, cited_sources: [] }), 202),
      "GET /courses/1/ai/drafts/7": () => { polls += 1; if (polls > 1) status = "draft"; return draft({ status }); },
      "PATCH /courses/1/ai/drafts/7": (c: { body: { content: unknown } }) => draft({ content: c.body.content, updated_at: "2026-11-02T00:00:00Z" }),
      "POST /courses/1/ai/drafts/7/accept": () => ({ draft: draft({ status: "accepted" }), created: { kcs: [1, 2] }, rebuild_job_id: null }),
    }));
    renderApp("/courses/1/ai");
    const user = userEvent.setup();
    expect(await screen.findByText(/Only the local model sees your course material/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("What to draft"), "kcs");
    await user.click(screen.getByRole("button", { name: "Draft with AI" }));
    expect(calls.find((c) => c.path === "/courses/1/ai/drafts" && c.method === "POST")!.body).toEqual({ kind: "kcs", module_id: null, focus: "", request: "" });
    expect(await screen.findByText("The local model is drafting…")).toBeInTheDocument();
    expect(await screen.findByText("Not visible to students until you accept it.", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("lecture1.pdf")).toBeInTheDocument();

    // the module is needed for knowledge components
    await user.selectOptions(await screen.findByLabelText("Module for the new knowledge components"), "10");
    await user.click(screen.getByRole("button", { name: "Accept and publish" }));
    expect(await screen.findByText("Accepted: 2 items created.")).toBeInTheDocument();
    expect(calls.find((c) => c.path.endsWith("/accept"))!.body).toEqual({ module_id: 10 });
  });

  it("sends a custom request with the chosen files (V4, V5)", async () => {
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/ai/drafts": [],
      "GET /courses/1/materials": { index_version: 1, rebuild_job_id: null, materials: [
        { id: 3, module_id: null, filename: "syllabus.md", size_bytes: 10, scan_status: "accepted", uploaded_at: "" },
        { id: 4, module_id: 10, filename: "lecture1.pdf", size_bytes: 10, scan_status: "accepted", uploaded_at: "" }] },
      "POST /courses/1/ai/drafts": () => reply(draft({ kind: "custom", status: "generating", content: {}, cited_sources: [] }), 202),
      "GET /courses/1/ai/drafts/7": () => draft({ kind: "custom", status: "generating", content: {}, cited_sources: [] }),
    }));
    renderApp("/courses/1/ai");
    const user = userEvent.setup();
    const button = await screen.findByRole("button", { name: "Draft with AI" });
    expect(button).toBeDisabled();  // a custom draft needs the request
    await user.type(screen.getByLabelText("What should be drafted?"), "Thesis topics from the lectures");
    await user.click(screen.getByLabelText("Some files"));
    await user.click(await screen.findByRole("checkbox", { name: /lecture1\.pdf/ }));
    await user.click(button);
    await waitFor(() => expect(calls.find((c) => c.path === "/courses/1/ai/drafts" && c.method === "POST")?.body).toEqual(
      { kind: "custom", focus: "", request: "Thesis topics from the lectures", module_id: null, material_ids: [4] }));
  });

  it("starts from a request handed over by Class overview (V8)", async () => {
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/ai/drafts": [], "GET /courses/1/materials": { index_version: 0, rebuild_job_id: null, materials: [] },
      "POST /courses/1/ai/drafts": () => reply(draft({ kind: "custom", status: "generating", content: {}, cited_sources: [] }), 202),
      "GET /courses/1/ai/drafts/7": () => draft({ kind: "custom", status: "generating", content: {}, cited_sources: [] }),
    }));
    renderApp({ pathname: "/courses/1/ai", state: { draft: { request: "Extra material on Resistance", moduleId: 10 } } });
    expect(await screen.findByLabelText("What should be drafted?")).toHaveValue("Extra material on Resistance");
    await userEvent.setup().click(screen.getByRole("button", { name: "Draft with AI" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/courses/1/ai/drafts" && c.method === "POST")?.body)
      .toMatchObject({ kind: "custom", request: "Extra material on Resistance", module_id: 10 }));
  });

  it("drafts with the cloud model only after the confirmation (V16)", async () => {
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/ai/drafts": [], "GET /courses/1/materials": { index_version: 0, rebuild_job_id: null, materials: [] },
      "POST /courses/1/ai/drafts": () => reply(draft({ kind: "custom", status: "generating", content: {}, cited_sources: [] }), 202),
      "GET /courses/1/ai/drafts/7": () => draft({ kind: "custom", status: "generating", content: {}, cited_sources: [] }),
    }));
    renderApp("/courses/1/ai");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("What should be drafted?"), "Summary of the open course page");
    await user.click(screen.getByLabelText("Cloud model, for public material only"));
    const button = screen.getByRole("button", { name: "Draft with AI" });
    expect(button).toBeDisabled();
    await user.click(screen.getByLabelText(/I confirm that this material is public/));
    await user.click(button);
    await waitFor(() => expect(calls.find((c) => c.path === "/courses/1/ai/drafts" && c.method === "POST")?.body)
      .toMatchObject({ kind: "custom", model: "cloud", confirm_cloud: true }));
  });

  it("uploads a file for this draft only (V6)", async () => {
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/ai/drafts": [],
      "GET /courses/1/materials": { index_version: 0, rebuild_job_id: null, materials: [] },
      "POST /courses/1/ai/drafts/upload": () => reply(draft({ kind: "custom", status: "generating", content: {}, cited_sources: [] }), 202),
      "GET /courses/1/ai/drafts/7": () => draft({ kind: "custom", status: "generating", content: {}, cited_sources: [] }),
    }));
    renderApp("/courses/1/ai");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("What should be drafted?"), "What this paper means for patients");
    await user.click(screen.getByLabelText("Upload a file"));
    await user.upload(screen.getByLabelText("File for this draft"), new File(["# Paper"], "paper.md", { type: "text/markdown" }));
    await user.click(screen.getByRole("button", { name: "Draft with AI" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/courses/1/ai/drafts/upload")).toBe(true));
    const form = calls.find((c) => c.path === "/courses/1/ai/drafts/upload")!.form!;
    expect((form.get("file") as File).name).toBe("paper.md");
    expect([form.get("kind"), form.get("request"), form.get("add_to_course"), form.get("module_id")])
      .toEqual(["custom", "What this paper means for patients", "false", null]);
  });

  it("shows the server's 422 message when an accept is refused", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/ai/drafts": [{ id: 7, kind: "check_items", module_id: null, status: "draft", created_at: "", updated_at: "" }],
      "GET /courses/1/ai/drafts/7": draft({ kind: "check_items", content: { items: [] } }),
      "POST /courses/1/ai/drafts/7/accept": () => reply({ detail: "unknown KC name: Resistance", code: "invalid" }, 422),
    }));
    renderApp("/courses/1/ai");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Open draft 7" }));
    await user.click(await screen.findByRole("button", { name: "Accept and publish" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("unknown KC name: Resistance");
    expect(screen.getByText("Not visible to students until you accept it.")).toBeInTheDocument();
  });

  it("filters the list by status", async () => {
    const calls = mockApi(instructorRoutes({ "GET /courses/1/ai/drafts": [] }));
    renderApp("/courses/1/ai");
    await userEvent.setup().selectOptions(await screen.findByLabelText("Status"), "accepted");
    await waitFor(() => expect(calls.some((c) => c.path === "/courses/1/ai/drafts" && c.query.get("status") === "accepted")).toBe(true));
  });
});

describe("class insights", () => {
  it("shows the suppressed state returned by the API", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/class-summary": { topic: "t", min_group: 5, suppressed: true },
      "GET /courses/1/insights": { min_group: 5, suppressed: true, kc_question_counts: [], misconception_counts: [] },
    }));
    renderApp("/courses/1/overview");
    expect(await screen.findByText("Fewer than 5 students contributed, so nothing is shown.")).toBeInTheDocument();
  });

  it("lists counts per topic and misconception", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/class-summary": { topic: "t", min_group: 5, suppressed: true },
      "GET /courses/1/insights": { min_group: 5, suppressed: false,
        kc_question_counts: [{ label: "K1", name: "Resistance", count: 12 }], misconception_counts: [{ label: "M1", name: "Current is used up", count: 6 }] },
    }));
    renderApp("/courses/1/overview");
    expect(await screen.findByText("Resistance")).toBeInTheDocument();
    expect(screen.getByText("Current is used up")).toBeInTheDocument();
  });
});

describe("cloud evaluation", () => {
  const evaluation = (over = {}) => ({ id: 3, status: "review", options: {}, results: [], report: {}, error: null, created_at: "", updated_at: "",
    questions: [{ id: 1, module_id: 10, module: "Ohm's law", type: "concept", question: "What is resistance?", reference: "Opposition to current." }], ...over });
  const routes = (extra = {}) => instructorRoutes({
    "GET /courses/1/ai/drafts": [],
    "GET /courses/1/ai/evaluations": [{ id: 3, status: "review", questions: 1, created_at: "", updated_at: "" }],
    "GET /courses/1/ai/evaluations/3": () => evaluation(),
    "PUT /courses/1/ai/evaluations/3/questions": () => evaluation(),
    ...extra,
  });
  const open = async () => {
    renderApp("/courses/1/ai");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("tab", { name: "Model evaluation" }));
    await user.click(await screen.findByRole("button", { name: "Open evaluation 3" }));
    return user;
  };

  it("sends nothing to the cloud until the explicit confirmation", async () => {
    const calls = mockApi(routes({ "POST /courses/1/ai/evaluations/3/run": () => reply(evaluation({ status: "running" }), 202) }));
    const user = await open();
    await user.click(await screen.findByRole("button", { name: "Run the comparison…" }));
    expect(await screen.findByText(/Your course material and these questions will be sent to the cloud model/)).toBeInTheDocument();
    expect(calls.some((c) => c.path.endsWith("/run"))).toBe(false);
    await user.click(screen.getByRole("button", { name: "Yes, send to the cloud and run" }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/run"))).toBe(true));
    expect(calls.find((c) => c.path.endsWith("/run"))!.body).toEqual({ confirm_cloud: true });
  });

  it("shows the refusal for a local-only course", async () => {
    mockApi(routes({ "POST /courses/1/ai/evaluations/3/run": () => reply({ detail: "this course uses the local model only: no cloud comparison", code: "conflict" }, 409) }));
    const user = await open();
    await user.click(await screen.findByRole("button", { name: "Run the comparison…" }));
    await user.click(await screen.findByRole("button", { name: "Yes, send to the cloud and run" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/local model only/);
  });

  it("shows the report table when done", async () => {
    mockApi(routes({
      "GET /courses/1/ai/evaluations/3": () => evaluation({ status: "done",
        report: { overall: { questions: 1, local_score: 3.5, cloud_score: 4.5 }, by_module: { "Ohm's law": { questions: 1, local_score: 3.5, cloud_score: 4.5 } }, by_type: {}, spot_checks: 0, spot_checks_agreeing: 0 },
        results: [{ question_id: 1, module: "Ohm's law", type: "concept", local: { score: 3 }, cloud: { score: 4 }, judge_reason: "Cloud was more complete.", spot_check: null }] }),
    }));
    await open();
    const table = await screen.findByRole("table", { name: "Evaluation report" });
    expect(table).toHaveTextContent("3.50");
    expect(table).toHaveTextContent("4.50");
    expect(screen.getByText(/Cloud was more complete/)).toBeInTheDocument();
  });
});
