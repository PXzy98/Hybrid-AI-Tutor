import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { instructorRoutes, mockApi, reply, renderApp } from "./helpers";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const members = [
  { id: 1, role: "instructor", status: "active", account_id: 2, username: "ida", display_name: "Ida Instructor", email: "ida@example.test", created_at: "2026-09-01T00:00:00Z", student_id: null },
  { id: 2, role: "student", status: "active", account_id: 3, username: "ana", display_name: "Ana Example", email: "ana@example.test", created_at: "2026-09-02T00:00:00Z", student_id: "stu-ana" },
  { id: 3, role: "student", status: "active", account_id: 4, username: "ben", display_name: "Ben Example", email: "ben@example.test", created_at: "2026-09-02T00:00:00Z", student_id: "stu-ben" },
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

  it("shows a clear not-visible state when the API answers 404, and requests nothing for students not opened", async () => {
    const calls = mockApi(routes());
    renderApp("/courses/1/students");
    const user = userEvent.setup();
    await screen.findByText("Ben Example");
    expect(screen.getByText("Not joined yet")).toBeInTheDocument();
    expect(calls.some((c) => c.path.includes("/overview"))).toBe(false);
    await user.click(screen.getByRole("button", { name: "View progress of Ben Example" }));
    expect(await screen.findByText("This student's progress is not visible.")).toBeInTheDocument();
    expect(screen.getByText(/visibility mode B/)).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Learning plan" })).not.toBeInTheDocument();
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

describe("class overview", () => {
  it("shows suppression returned by the API instead of numbers", async () => {
    mockApi(instructorRoutes({ "GET /courses/1/class-summary": { topic: "t", min_group: 5, suppressed: true } }));
    renderApp("/courses/1/overview");
    expect(await screen.findByText(/Fewer than 5 students have a learning profile/)).toBeInTheDocument();
  });
});
