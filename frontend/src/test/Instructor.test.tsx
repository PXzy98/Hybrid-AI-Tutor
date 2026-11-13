import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { instructorRoutes, mockApi, reply, renderApp } from "./helpers";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const members = [
  { id: 1, role: "instructor", status: "active", account_id: 2, username: "ida", display_name: "Ida Instructor", email: "ida@example.test", created_at: "2026-09-01T00:00:00Z", student_id: null },
  { id: 2, role: "student", status: "active", account_id: 3, username: "ana", display_name: "Ana Example", email: "ana@example.test", created_at: "2026-09-02T00:00:00Z", student_id: "stu-ana", visible_to_instructor: true },
  { id: 3, role: "student", status: "active", account_id: 4, username: "ben", display_name: "Ben Example", email: "ben@example.test", created_at: "2026-09-02T00:00:00Z", student_id: "stu-ben", visible_to_instructor: false },
  { id: 4, role: "student", status: "pending", account_id: null, username: null, display_name: null, email: "cy@example.test", created_at: "2026-09-03T00:00:00Z", student_id: null },
];

describe("instructor students", () => {
  const routes = (extra = {}) => instructorRoutes({
    "GET /courses/1/members": members,
    "GET /courses/1/kcs": [{ id: 5, module_id: 10, code: "K1", name: "Resistance", definition: "", difficulty: "basic", status: "active", prerequisite_ids: [] }],
    "GET /courses/1/students/stu-ana/overview": { student_id: "stu-ana", visible_since: "2026-11-01T00:00:00Z", kcs: [{ kc_code: "K1", level: "basic", p_mastery: 0.3 }], open_misconceptions: 1, checks_answered: 4, last_active: null },
    "GET /courses/1/students/stu-ana/plan": () => reply({ detail: "none", code: "not_found" }, 404),
    "GET /courses/1/students/stu-ben/overview": () => reply({ detail: "This student's individual data is not available.", code: "not_found" }, 404),
    ...extra,
  });

  it("shows each student's visibility state and only offers the overview when the API says it is visible", async () => {
    const calls = mockApi(routes());
    renderApp("/courses/1/students");
    await screen.findByText("Ben Example");
    const row = (name: string) => screen.getByText(name).closest("tr")!;
    expect(within(row("Ana Example")).getByText("Visible")).toBeInTheDocument();
    expect(within(row("Ben Example")).getByText("Not visible")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View progress of Ana Example" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "View progress of Ben Example" })).not.toBeInTheDocument();
    expect(screen.getByText("Not joined yet")).toBeInTheDocument();
    expect(calls.some((c) => c.path.includes("/overview"))).toBe(false);
  });

  it("still explains a 404 from the overview as not visible", async () => {
    mockApi(routes({
      "GET /courses/1/members": members.map((m) => (m.student_id === "stu-ben" ? { ...m, visible_to_instructor: true } : m)),
    }));
    renderApp("/courses/1/students");
    await userEvent.setup().click(await screen.findByRole("button", { name: "View progress of Ben Example" }));
    expect(await screen.findByText("This student's progress is not visible.")).toBeInTheDocument();
    expect(screen.getByText(/visibility mode B/)).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Learning plan" })).not.toBeInTheDocument();
  });

  it("asks the backend on every open and never shows earlier data after a refusal", async () => {
    let overviewCalls = 0;
    const calls = mockApi(routes({
      "GET /courses/1/students/stu-ana/overview": () => {
        overviewCalls += 1;
        return overviewCalls === 1
          ? { student_id: "stu-ana", visible_since: "2026-11-01T00:00:00Z", kcs: [{ kc_code: "K1", level: "basic", p_mastery: 0.3 }], open_misconceptions: 1, checks_answered: 4, last_active: null }
          : reply({ detail: "This student's individual data is not available.", code: "not_found" }, 404);
      },
    }));
    renderApp("/courses/1/students");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "View progress of Ana Example" }));
    expect(await screen.findByText("Check questions answered:")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "View progress of Ana Example" }));
    await waitFor(() => expect(screen.queryByText("Check questions answered:")).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "View progress of Ana Example" }));
    expect(await screen.findByText("This student's progress is not visible.")).toBeInTheDocument();
    expect(screen.queryByText("Check questions answered:")).not.toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Learning plan" })).not.toBeInTheDocument();
    expect(calls.filter((c) => c.path.endsWith("/overview"))).toHaveLength(2);
  });

  it("shows a visible student's overview and saves the learning plan", async () => {
    const calls = mockApi(routes({
      "PUT /courses/1/students/stu-ana/plan": (c: { body: unknown }) => ({ ...(c.body as object), updated_at: "2026-11-05T00:00:00Z" }),
    }));
    renderApp("/courses/1/students");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "View progress of Ana Example" }));
    expect(await screen.findByText("Check questions answered:")).toBeInTheDocument();
    const form = await screen.findByRole("form", { name: "Learning plan" });
    await user.selectOptions(screen.getByLabelText("Goal level"), "advanced");
    await user.click(screen.getByRole("checkbox", { name: /K1 Resistance/ }));
    await user.type(screen.getByLabelText("Notes"), "Work on circuits.");
    await user.click(screen.getByRole("button", { name: "Save plan" }));
    expect(await screen.findByText("Plan saved.")).toBeInTheDocument();
    const put = calls.find((c) => c.method === "PUT")!;
    expect(put.headers["X-CSRF-Token"]).toBe("test-token");
    expect(put.body).toEqual({ focus_kcs: ["K1"], goal: "advanced", notes: "Work on circuits." });
    expect(form).toBeInTheDocument();
  });
});

describe("member import", () => {
  it("uploads the CSV and shows the import report", async () => {
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/members": members,
      "GET /courses/1/invite": { expires_at: null, uses: 2, max_uses: null, created_at: "2026-09-01T00:00:00Z", expired: false, code: "JOIN-0001" },
      "POST /courses/1/members/import": { added: ["a@example.test"], pending: ["b@example.test"], unchanged: [], rejected: [{ row: 4, email: "bad", reason: "not an e-mail address" }] },
    }));
    renderApp("/courses/1/members");
    const user = userEvent.setup();
    expect(await screen.findByLabelText("Invitation code")).toHaveTextContent("JOIN-0001");
    const file = new File(["email,display_name\na@example.test,Ann\n"], "class.csv", { type: "text/csv" });
    await user.upload(await screen.findByLabelText("CSV file"), file);
    await user.click(screen.getByRole("button", { name: "Import" }));
    expect(await screen.findByText("1 added")).toBeInTheDocument();
    expect(screen.getByText("1 waiting for their invitation code")).toBeInTheDocument();
    expect(screen.getByText(/not an e-mail address/)).toBeInTheDocument();
    const upload = calls.find((c) => c.path === "/courses/1/members/import")!;
    expect((upload.form!.get("file") as File).name).toBe("class.csv");
    expect(upload.headers["X-CSRF-Token"]).toBe("test-token");
  });
});

describe("end of term", () => {
  it("needs the course code typed in the dialog, then exports and offers the download", async () => {
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: () => undefined }));
    const calls = mockApi(instructorRoutes({
      "POST /courses/1/end-term": { export_id: "exp-1", expires_at: "2026-12-30T00:00:00Z", students_removed: 3, students_exported: 3, deleted: {} },
      "GET /courses/1/exports/exp-1": () => new Response("zip", { headers: { "Content-Disposition": 'attachment; filename="ECE 1000-exp-1.zip"' } }),
    }));
    renderApp("/courses/1/endterm");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "End the term…" }));
    const confirm = await screen.findByRole("button", { name: "Export and delete" });
    expect(confirm).toBeDisabled();
    expect(calls.some((c) => c.path.endsWith("/end-term"))).toBe(false);
    await user.type(screen.getByLabelText("Type ECE 1000 to confirm"), "ECE 1000");
    expect(confirm).toBeEnabled();
    await user.click(confirm);
    expect(await screen.findByText("3 students exported, 3 removed.")).toBeInTheDocument();
    expect(calls.find((c) => c.path.endsWith("/end-term"))!.body).toEqual({ confirm: true });
    await user.click(screen.getByRole("button", { name: "Download the export" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/courses/1/exports/exp-1")).toBe(true));
  });
});

describe("export before the end of term", () => {
  it("creates an export and offers the download without ending the term", async () => {
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: () => undefined }));
    const calls = mockApi(instructorRoutes({
      "POST /courses/1/exports": { export_id: "exp-0", expires_at: "2026-12-30T00:00:00Z", students_exported: 2 },
      "GET /courses/1/exports/exp-0": () => new Response("zip", { headers: { "Content-Disposition": 'attachment; filename="ECE 1000-exp-0.zip"' } }),
    }));
    renderApp("/courses/1/endterm");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Create an export" }));
    expect(await screen.findByText("Export ready: 2 individual overviews (visibility mode B only).")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Download the export" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/courses/1/exports/exp-0")).toBe(true));
    expect(calls.some((c) => c.path.endsWith("/end-term"))).toBe(false); // nothing was deleted
  });
});

describe("class overview", () => {
  it("shows suppression returned by the API instead of numbers", async () => {
    mockApi(instructorRoutes({ "GET /courses/1/class-summary": { topic: "t", min_group: 5, suppressed: true } }));
    renderApp("/courses/1/overview");
    expect(await screen.findByText(/Fewer than 5 students have a learning profile/)).toBeInTheDocument();
  });
});

describe("materials", () => {
  const file = { id: 1, module_id: null as number | null, filename: "syllabus.pdf", size_bytes: 20480, scan_status: "clean", uploaded_at: "2026-11-01T00:00:00Z" };

  it("uploads with a module, shows the index rebuild until the job is done", async () => {
    let list = { index_version: 1, rebuild_job_id: null as number | null, materials: [file] };
    let polls = 0;
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/materials": () => list,
      "POST /courses/1/materials": () => {
        list = { index_version: 1, rebuild_job_id: 5, materials: [file, { ...file, id: 2, module_id: 10, filename: "week1.md" }] };
        return reply({ material: list.materials[1], job_id: 5 }, 201);
      },
      "GET /courses/1/jobs/5": () => {
        polls += 1;
        const done = polls > 1;
        if (done) list = { ...list, index_version: 2, rebuild_job_id: null };
        return { id: 5, kind: "index.rebuild", status: done ? "done" : "running", progress: 0, error: null, created_at: "", started_at: null, finished_at: null };
      },
    }));
    renderApp("/courses/1/materials");
    const user = userEvent.setup();
    expect(await screen.findByText("syllabus.pdf")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Module"), "10");
    await user.upload(screen.getByLabelText("File"), new File(["# Week 1"], "week1.md", { type: "text/markdown" }));
    await user.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByText(/Rebuilding the search index/)).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST" && c.path === "/courses/1/materials")!;
    expect((post.form!.get("file") as File).name).toBe("week1.md");
    expect(post.form!.get("module_id")).toBe("10");
    expect(post.headers["X-CSRF-Token"]).toBe("test-token");
    expect(await screen.findByText("week1.md")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/Rebuilding the search index/)).not.toBeInTheDocument(), { timeout: 5000 });
    expect(await screen.findByText("Index version 2")).toBeInTheDocument();
  });

  it("shows the server's message naming the privacy findings when a file is refused", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/materials": { index_version: 1, rebuild_job_id: null, materials: [] },
      "POST /courses/1/materials": () => reply({ detail: "The file looks like it contains student data (STUDENT_ID, PERSON).", code: "invalid" }, 422),
    }));
    renderApp("/courses/1/materials");
    const user = userEvent.setup();
    await user.upload(await screen.findByLabelText("File"), new File(["x"], "grades.txt", { type: "text/plain" }));
    await user.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("STUDENT_ID, PERSON");
  });

  it("asks for confirmation before deleting a file", async () => {
    let list = { index_version: 1, rebuild_job_id: null as number | null, materials: [file] };
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/materials": () => list,
      "DELETE /courses/1/materials/1": () => { list = { ...list, materials: [] }; return new Response(null, { status: 204 }); },
    }));
    renderApp("/courses/1/materials");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Delete syllabus.pdf" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    expect(await screen.findByText(/search index is rebuilt without it/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete file" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/courses/1/materials/1")).toBe(true));
    expect(await screen.findByText("No files yet.")).toBeInTheDocument();
  });
});
