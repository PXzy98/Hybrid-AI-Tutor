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
    expect(await screen.findByText("temp-fictional-123")).toBeInTheDocument();
    await user.clear(screen.getByLabelText("Search by name or e-mail"));
    await user.click(screen.getByRole("button", { name: "Disable Ana Example" }));
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
});
