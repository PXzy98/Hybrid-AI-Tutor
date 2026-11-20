import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ME_INSTRUCTOR, mockApi, renderApp } from "./helpers";

afterEach(() => vi.unstubAllGlobals());

const ana = { account_id: 11, display_name: "Ana Example", email: "ana@uottawa.ca", active: true, must_change_password: false,
  created_at: "2026-09-01T00:00:00Z", last_login_at: "2026-11-18T00:00:00Z", courses: 2 };
const ben = { ...ana, account_id: 12, display_name: "Ben Example", email: "ben@uottawa.ca", courses: 0, last_login_at: null };

const admin = (extra = {}) => ({
  "GET /auth/me": { ...ME_INSTRUCTOR, system_role: "admin" }, "GET /courses": [],
  "GET /admin/instructors": [], "GET /admin/settings": { values: {}, version: 1, apply_state: "applied" }, "GET /admin/model-endpoints": [],
  "GET /admin/students": [ana, ben], ...extra,
});

describe("student accounts (V9)", () => {
  it("lists, searches, deactivates and resets", async () => {
    const calls = mockApi(admin({
      "PATCH /admin/students/11": { ...ana, active: false },
      "POST /admin/students/12/reset-password": { temporary_password: "temp-fictional-123" },
    }));
    renderApp("/admin");
    const user = userEvent.setup();
    const table = await screen.findByRole("table", { name: "Student accounts" });
    expect(within(table).getByText("Ana Example").closest("tr")!).toHaveTextContent("2");
    await user.type(screen.getByLabelText("Search by name or e-mail"), "ben@");
    expect(screen.queryByText("Ana Example")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reset the password of Ben Example" }));
    // V17 W11: confirmed first, then shown in the row under the account
    expect(screen.getByRole("dialog")).toHaveTextContent("Ben Example gets a new temporary password");
    expect(calls.some((c) => c.path.endsWith("/reset-password"))).toBe(false);
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    const note = await screen.findByText("temp-fictional-123");
    expect(note.closest("tr")!.previousElementSibling).toHaveTextContent("Ben Example");
    await user.clear(screen.getByLabelText("Search by name or e-mail"));
    await user.click(screen.getByRole("button", { name: "Deactivate Ana Example" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ active: false }));
  });

  it("asks before deleting an account", async () => {
    const calls = mockApi(admin({ "DELETE /admin/students/12": () => new Response(null, { status: 204 }) }));
    renderApp("/admin");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Delete the account of Ben Example" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("cannot be undone");
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    await user.click(screen.getByRole("button", { name: "Delete the account" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/admin/students/12")).toBe(true));
  });

  it("clears the temporary password when another action starts or that account is deleted", async () => {
    const calls = mockApi(admin({
      "POST /admin/students/12/reset-password": { temporary_password: "temp-fictional-123" },
      "PATCH /admin/students/11": { ...ana, active: false },
      "DELETE /admin/students/12": () => new Response(null, { status: 204 }),
      "GET /admin/system-statistics": { students_enrolled: 0, active_students_7d: 0, questions_7d: null, min_group: 5, courses: [] },
    }));
    renderApp("/admin");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Reset the password of Ben Example" }));
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByText("temp-fictional-123")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Deactivate Ana Example" }));
    expect(screen.queryByText("temp-fictional-123")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reset the password of Ben Example" }));
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByText("temp-fictional-123")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete the account of Ben Example" }));
    await user.click(screen.getByRole("button", { name: "Delete the account" }));
    await waitFor(() => expect(screen.queryByText("temp-fictional-123")).not.toBeInTheDocument());
    const statistics = () => calls.filter((c) => c.path.endsWith("statistics")).length;
    await waitFor(() => expect(statistics()).toBeGreaterThan(1)); // refetched after the delete
  });

  it("does not carry a failed delete over to the next dialog", async () => {
    mockApi(admin({ "DELETE /admin/students/12": () => new Response(JSON.stringify({ detail: "boom", code: "invalid" }), { status: 500 }) }));
    renderApp("/admin");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Delete the account of Ben Example" }));
    await user.click(screen.getByRole("button", { name: "Delete the account" }));
    await within(screen.getByRole("dialog")).findByRole("alert");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Delete the account of Ana Example" }));
    expect(within(screen.getByRole("dialog")).queryByRole("alert")).not.toBeInTheDocument();
  });
});
