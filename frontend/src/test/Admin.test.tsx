import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { COURSE, ME_INSTRUCTOR, ME_STUDENT, instructorRoutes, mockApi, reply, renderApp } from "./helpers";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const ME_ADMIN = { ...ME_INSTRUCTOR, account_id: 9, username: "ada", display_name: "Ada Admin", system_role: "admin" as const };
const staff = [
  { account_id: 9, username: "ada@example.test", email: "ada@example.test", display_name: "Ada Admin", role: "admin", active: true, must_change_password: false, last_login_at: null },
  { account_id: 2, username: "ida@example.test", email: "ida@example.test", display_name: "Ida Instructor", role: "instructor", active: true, must_change_password: false, last_login_at: null },
];
const settings = { values: { weak_evidence: true, level_basic_below: 0.4, level_advanced_above: 0.8, level_hysteresis: 0.05, default_routing_method: "lr",
  local_llm_url: "http://localhost:11434", local_llm_model: "fictional-model", enabled_course_types: ["ece"], default_local_endpoint_id: null, default_cloud_endpoint_id: null },
  version: 3, apply_state: "applied" };
const endpoint = { id: 4, course_id: null, name: "Lab server", kind: "openai_compat", base_url: "https://models.example.test/v1", model: "fictional-large",
  trust: "external", api_key_last4: "4321", last_test_ok_at: null };

const adminRoutes = (extra: Record<string, unknown> = {}) => ({
  "GET /auth/me": ME_ADMIN,
  "GET /courses": [],
  "GET /admin/instructors": staff,
  "GET /admin/settings": settings,
  "GET /admin/model-endpoints": [endpoint],
  ...extra,
});

describe("administration link", () => {
  it("is shown to administrators only", async () => {
    mockApi(adminRoutes());
    const admin = renderApp("/courses");
    expect(await screen.findByRole("link", { name: "Administration" })).toHaveAttribute("href", "/admin");
    admin.unmount();

    mockApi(instructorRoutes({ "GET /courses": [] }));
    const instructor = renderApp("/courses");
    await screen.findByRole("button", { name: "New course" });
    expect(screen.queryByRole("link", { name: "Administration" })).not.toBeInTheDocument();
    instructor.unmount();

    mockApi({ "GET /auth/me": ME_STUDENT, "GET /courses": [COURSE] });
    renderApp("/admin");
    expect(await screen.findByText("Only administrators can open this page.")).toBeInTheDocument();
  });
});

describe("system administration", () => {
  it("creates an instructor account and shows the temporary password once", async () => {
    let list = staff;
    const calls = mockApi(adminRoutes({
      "GET /admin/instructors": () => list,
      "POST /admin/instructors": () => {
        list = [...staff, { ...staff[1], account_id: 5, email: "new@example.test", display_name: "New Person", must_change_password: true }];
        return reply({ ...list[2], temporary_password: "temp-pass-123" }, 201);
      },
    }));
    renderApp("/admin");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("E-mail"), "new@example.test");
    await user.type(screen.getByLabelText("Display name"), "New Person");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("temp-pass-123")).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST")!;
    expect(post.body).toEqual({ email: "new@example.test", display_name: "New Person", role: "instructor" });
    expect(post.headers["X-CSRF-Token"]).toBe("test-token");
    expect(await screen.findByText("New Person")).toBeInTheDocument();
  });

  it("disables an account", async () => {
    const calls = mockApi(adminRoutes({ "PATCH /admin/instructors/2": (c: { body: unknown }) => ({ ...staff[1], ...(c.body as object) }) }));
    renderApp("/admin");
    await userEvent.setup().click(await screen.findByRole("button", { name: "Disable Ida Instructor" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ active: false }));
    expect(screen.getByRole("button", { name: "Disable Ada Admin" })).toBeDisabled(); // not your own account
  });

  it("saves the system settings with the version that was read and explains a 409", async () => {
    let attempts = 0;
    const calls = mockApi(adminRoutes({
      "PUT /admin/settings": () => {
        attempts += 1;
        return reply({ detail: "settings changed since they were read", code: "conflict" }, 409);
      },
    }));
    renderApp("/admin");
    const user = userEvent.setup();
    const field = await screen.findByLabelText("Basic level below (mastery)");
    await user.clear(field);
    await user.type(field, "0.35");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText(/Someone else changed the settings/)).toBeInTheDocument();
    const put = calls.find((c) => c.method === "PUT")!;
    expect(attempts).toBe(1);
    expect(put.body).toMatchObject({ version: 3, values: { level_basic_below: 0.35 } });
    // the latest values were loaded again
    expect(calls.filter((c) => c.method === "GET" && c.path === "/admin/settings").length).toBeGreaterThan(1);
  });

  it("lists model connections with their trust level and never shows a stored key", async () => {
    const calls = mockApi(adminRoutes({
      "PATCH /admin/model-endpoints/4": (c: { body: unknown }) => ({ ...endpoint, ...(c.body as object) }),
    }));
    renderApp("/admin");
    const user = userEvent.setup();
    const row = await screen.findByRole("row", { name: /Lab server/ });
    expect(within(row).getByText("External")).toBeInTheDocument();
    expect(within(row).getByText("Set (ends in 4321)")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Edit Lab server" }));
    const dialog = await screen.findByRole("dialog");
    const key = within(dialog).getByLabelText("API key (optional)") as HTMLInputElement;
    expect(key.type).toBe("password");
    expect(key.value).toBe("");
    expect(dialog.textContent).not.toContain("4321");
    await user.clear(within(dialog).getByLabelText("Model"));
    await user.type(within(dialog).getByLabelText("Model"), "fictional-small");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    const patch = calls.find((c) => c.method === "PATCH")!;
    expect(patch.body).toMatchObject({ model: "fictional-small", trust: "external" });
    expect(patch.body).not.toHaveProperty("api_key"); // an empty field keeps the stored key
  });

  it("asks to confirm control of a trusted local connection and shows the server's refusal", async () => {
    const calls = mockApi(adminRoutes({
      "POST /admin/model-endpoints": () => reply({ detail: "connection test failed: connection refused", code: "invalid" }, 422),
    }));
    renderApp("/admin");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Add connection" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).queryByLabelText(/I control this service/)).not.toBeInTheDocument();
    await user.type(within(dialog).getByLabelText("Name"), "Local box");
    await user.type(within(dialog).getByLabelText("Address (URL)"), "http://10.0.0.5:11434");
    await user.type(within(dialog).getByLabelText("Model"), "fictional-small");
    await user.selectOptions(within(dialog).getByLabelText("Trust level"), "trusted_local");
    await user.click(within(dialog).getByLabelText(/I control this service/));
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("connection test failed");
    expect(calls.find((c) => c.method === "POST")!.body).toMatchObject({ trust: "trusted_local", confirm_controlled: true, kind: "ollama" });
  });
});

describe("course content", () => {
  it("shows the server's message when a YAML import is refused", async () => {
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/kcs": [], "GET /courses/1/check-items": [], "GET /courses/1/misconceptions": [],
      "POST /courses/1/content/import": () => reply({ detail: "M1/kcs.yaml: line 3: unknown field 'difficulty_level'", code: "invalid" }, 422),
    }));
    renderApp("/courses/1/content");
    const user = userEvent.setup();
    await user.upload(await screen.findByLabelText("ZIP file"), new File(["zip"], "content.zip", { type: "application/zip" }));
    await user.click(screen.getByRole("button", { name: "Import content" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("M1/kcs.yaml: line 3: unknown field 'difficulty_level'");
    expect((calls.find((c) => c.method === "POST")!.form!.get("file") as File).name).toBe("content.zip");
  });

  it("reports what a YAML import created", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/kcs": [], "GET /courses/1/check-items": [], "GET /courses/1/misconceptions": [],
      "POST /courses/1/content/import": { modules: 2, kcs: 5, items: 9, misconceptions: 3 },
    }));
    renderApp("/courses/1/content");
    const user = userEvent.setup();
    await user.upload(await screen.findByLabelText("ZIP file"), new File(["zip"], "content.zip", { type: "application/zip" }));
    await user.click(screen.getByRole("button", { name: "Import content" }));
    expect(await screen.findByText("Imported 2 modules, 5 knowledge components, 9 check items and 3 misconceptions.")).toBeInTheDocument();
  });

  it("exports the content from the API", async () => {
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: () => undefined }));
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/kcs": [], "GET /courses/1/check-items": [], "GET /courses/1/misconceptions": [],
      "GET /courses/1/content/export": () => new Response("zip", { status: 200, headers: { "Content-Disposition": 'attachment; filename="ECE_1000-content.zip"' } }),
    }));
    renderApp("/courses/1/content");
    await userEvent.setup().click(await screen.findByRole("button", { name: "Export content" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/courses/1/content/export")).toBe(true));
  });

  it("creates a misconception", async () => {
    let list: unknown[] = [];
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/kcs": [{ id: 5, module_id: 10, code: "K1", name: "Resistance", definition: "", difficulty: "basic", status: "active", prerequisite_ids: [] }],
      "GET /courses/1/check-items": [],
      "GET /courses/1/misconceptions": () => list,
      "POST /courses/1/misconceptions": (c: { body: unknown }) => {
        const created = { id: 7, ...(c.body as object) };
        list = [created];
        return reply(created, 201);
      },
    }));
    renderApp("/courses/1/content");
    const user = userEvent.setup();
    expect(await screen.findByText("No misconceptions yet.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add misconception" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Code"), "MC1");
    await user.type(within(dialog).getByLabelText("The wrong idea"), "Current is used up by a resistor.");
    await user.type(within(dialog).getByLabelText("Correction"), "Current is the same everywhere in a series loop.");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Current is used up by a resistor.")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ kc_id: 5, code: "MC1", statement: "Current is used up by a resistor.",
      correction: "Current is the same everywhere in a series loop.", status: "active" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("retires a misconception", async () => {
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/kcs": [{ id: 5, module_id: 10, code: "K1", name: "Resistance", definition: "", difficulty: "basic", status: "active", prerequisite_ids: [] }],
      "GET /courses/1/check-items": [],
      "GET /courses/1/misconceptions": [{ id: 7, kc_id: 5, code: "MC1", statement: "Wrong idea", correction: "Right idea", status: "active" }],
      "PATCH /courses/1/misconceptions/7": { id: 7, kc_id: 5, code: "MC1", statement: "Wrong idea", correction: "Right idea", status: "retired" },
    }));
    renderApp("/courses/1/content");
    await userEvent.setup().click(await screen.findByRole("button", { name: "Retire MC1" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ status: "retired" }));
  });
});

describe("course settings", () => {
  const settingsRoutes = (extra = {}) => instructorRoutes({
    "GET /courses/1/settings": { values: { visibility_mode: "B", local_only: false, routing_preference: "default", show_routing_progress: true }, version: 1 },
    "GET /courses/1/model-endpoints": [],
    ...extra,
  });

  it("explains that a course with students cannot be archived", async () => {
    const calls = mockApi(settingsRoutes({
      "POST /courses/1/archive": () => reply({ detail: "The course still has students. End the term first.", code: "conflict" }, 409),
    }));
    renderApp("/courses/1/settings");
    await userEvent.setup().click(await screen.findByRole("button", { name: "Archive course" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The course was not archived. End the term first.");
    expect(alert).toHaveTextContent("The course still has students.");
    expect(calls.find((c) => c.path === "/courses/1/archive")!.headers["X-CSRF-Token"]).toBe("test-token");
  });

  it("lists the course's model connections", async () => {
    mockApi(settingsRoutes({ "GET /courses/1/model-endpoints": [{ ...endpoint, id: 8, course_id: 1, name: "Course server" }] }));
    renderApp("/courses/1/settings");
    expect(await screen.findByText("Course server")).toBeInTheDocument();
  });
});
