import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import ClassSummaryPage from "../pages/admin/ClassSummary";
import StudentsPage from "../pages/admin/Students";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function renderPage(page: JSX.Element) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter>{page}</MemoryRouter></QueryClientProvider>);
}

/** Routes fetch calls by "METHOD path" (query string removed). */
function stubApi(routes: Record<string, () => Response>) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url.split("?")[0]}`;
    if (!routes[key]) throw new Error(`unexpected ${key}`);
    return routes[key]();
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const ACCOUNT = { id: 7, username: "s.one", display_name: "S One", active: true, must_change_password: true,
                  created_at: "2026-10-12T10:00:00Z", last_login_at: null };

afterEach(() => vi.unstubAllGlobals());

describe("Students", () => {
  it("adds a student and shows the temporary password once", async () => {
    let list = [] as unknown[];
    const fetchMock = stubApi({
      "GET /api/v1/admin/students": () => json(list),
      "POST /api/v1/admin/students": () => {
        list = [ACCOUNT];
        return json({ account: ACCOUNT, temporary_password: "tmp-Pass-123" }, 201);
      },
    });
    const user = userEvent.setup();
    renderPage(<StudentsPage />);
    expect(await screen.findByText("No students yet.")).toBeInTheDocument();
    expect(screen.getByText(/Do not use real student numbers as usernames/)).toBeInTheDocument();

    await user.type(screen.getByLabelText("Username"), "s.one");
    await user.click(screen.getByRole("button", { name: "Add student" }));

    expect(await screen.findByTestId("temp-password")).toHaveTextContent("tmp-Pass-123");
    expect(screen.getByRole("button", { name: "Copy" })).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST")!;
    expect(JSON.parse(post[1]!.body as string)).toEqual({ username: "s.one", display_name: "" });
    expect(await screen.findByText("s.one")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Done" }));
    expect(screen.queryByTestId("temp-password")).not.toBeInTheDocument();
  });

  it("deletes only after the username is typed", async () => {
    const fetchMock = stubApi({
      "GET /api/v1/admin/students": () => json([ACCOUNT]),
      "DELETE /api/v1/admin/students/7": () => new Response(null, { status: 204 }),
    });
    const user = userEvent.setup();
    renderPage(<StudentsPage />);
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(/learning profile/)).toBeInTheDocument();
    const confirm = within(dialog).getByRole("button", { name: "Delete permanently" });
    expect(confirm).toBeDisabled();
    await user.type(within(dialog).getByLabelText(/Type the username/), "s.one");
    await user.click(confirm);
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(true);
  });
});

describe("ClassSummary", () => {
  it("explains suppression for a small class", async () => {
    stubApi({
      "GET /api/v1/topics": () => json([{ id: "high_blood_pressure", name: "High Blood Pressure", kc_count: 6, reviewed_item_count: 0 }]),
      "GET /api/v1/admin/class-summary": () => json({ topic: "high_blood_pressure", min_group: 5, suppressed: true }),
    });
    renderPage(<ClassSummaryPage />);
    expect(await screen.findByText(/Fewer than 5 students have a learning profile/)).toBeInTheDocument();
  });

  it("draws bars with suppressed cells pooled as hidden", async () => {
    stubApi({
      "GET /api/v1/topics": () => json([]),
      "GET /api/v1/admin/class-summary": () => json({
        topic: "high_blood_pressure", min_group: 5, suppressed: false, students: 9,
        kcs: [{ kc_id: "HBP.1", name: "Blood pressure numbers",
                counts: { not_assessed: 0, basic: 6, intermediate: null, advanced: null, mastered: 0 } }],
        misconceptions: [{ misconception_id: "HBP.MC5", kc_id: "HBP.1", statement: "The heart stops.", students: 5 }],
        misconceptions_hidden: 2,
      }),
    });
    renderPage(<ClassSummaryPage />);
    const bar = await screen.findByRole("img", { name: /Blood pressure numbers/ });
    expect(bar).toHaveAccessibleName(expect.stringContaining("Intermediate: fewer than 5"));
    expect(within(bar).getByText("6")).toBeInTheDocument();
    expect(within(bar).getByText("<5")).toBeInTheDocument();
    expect(screen.getByText("5 students")).toBeInTheDocument();
    expect(screen.getByText(/2 more misconception/)).toBeInTheDocument();
  });
});
